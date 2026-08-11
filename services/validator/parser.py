import os
import re
import asyncio
import configparser
import unicodedata
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import quote
from sqlalchemy import create_engine, text, bindparam
import httpx
from shared_lib.schemas import ValidationResult, ValidationRequestPayload
from shared_lib.logger import setup_logger

logger = setup_logger("validator-parser")

MEDIAWIKI_API_URL = os.getenv("MEDIAWIKI_API_URL", "https://bn.wiktionary.org/w/api.php")

def get_toolforge_credentials():
    cnf_path = os.path.expanduser("~/replica.my.cnf")
    if os.path.exists(cnf_path):
        try:
            config = configparser.ConfigParser()
            config.read(cnf_path)
            if 'client' in config:
                user = config['client'].get('user', '').strip("'\"")
                password = config['client'].get('password', '').strip("'\"")
                return user, password
        except Exception as e:
            logger.error(f"Error reading replica.my.cnf: {e}")
    return None, None

WIKI_DB_HOST = os.getenv("WIKI_DB_HOST", "bnwiktionary.web.db.svc.wikimedia.cloud")
WIKI_DB_NAME = os.getenv("WIKI_DB_NAME", "bnwiktionary_p")
WIKI_DB_PORT = int(os.getenv("WIKI_DB_PORT", "3306"))
WIKI_DB_USER = os.getenv("WIKI_DB_USER", os.getenv("TOOL_REPLICA_USER"))
WIKI_DB_PASSWORD = os.getenv("WIKI_DB_PASSWORD", os.getenv("TOOL_REPLICA_PASSWORD"))

if not WIKI_DB_USER or not WIKI_DB_PASSWORD:
    tf_user, tf_pass = get_toolforge_credentials()
    if tf_user and tf_pass:
        WIKI_DB_USER = WIKI_DB_USER or tf_user
        WIKI_DB_PASSWORD = WIKI_DB_PASSWORD or tf_pass

wiki_engine = None
if WIKI_DB_USER and WIKI_DB_PASSWORD:
    try:
        wiki_db_url = f"mysql+pymysql://{WIKI_DB_USER}:{WIKI_DB_PASSWORD}@{WIKI_DB_HOST}:{WIKI_DB_PORT}/{WIKI_DB_NAME}?charset=utf8mb4"
        wiki_engine = create_engine(
            wiki_db_url,
            pool_size=5,
            max_overflow=10,
            pool_recycle=3600,
            pool_pre_ping=True
        )
        logger.info(f"Wiki replica engine initialized: {WIKI_DB_HOST}/{WIKI_DB_NAME} as {WIKI_DB_USER}")
    except Exception as e:
        logger.error(f"Could not initialize Wiki Replica DB engine: {e}")
else:
    logger.warning("Wiki replica engine NOT initialized")


def query_wiki_replica_batch(titles: list) -> Optional[dict]:
    """
    Queries the Wikimedia MariaDB replica for bnwiktionary_p to validate article creation date & creator.
    """
    if not wiki_engine or not titles:
        logger.debug("Skipping replica query: wiki_engine not available or empty titles")
        return None

    title_map = {}  # db_fmt -> original_title
    db_titles_set = set()
    for t in titles:
        clean = t.strip()
        if clean:
            db_fmt = clean.replace(" ", "_")
            if db_fmt not in title_map:
                title_map[db_fmt] = clean
            db_titles_set.add(db_fmt)
            db_fmt_cap = db_fmt[0].upper() + db_fmt[1:] if db_fmt else db_fmt
            if db_fmt_cap not in title_map:
                title_map[db_fmt_cap] = clean
            db_titles_set.add(db_fmt_cap)

    db_titles = list(db_titles_set)
    if not db_titles:
        return {}

    results = {}
    chunk_size = 500

    try:
        with wiki_engine.connect() as conn:
            for i in range(0, len(db_titles), chunk_size):
                chunk = db_titles[i:i + chunk_size]
                query = text("""
                    SELECT 
                        CONVERT(p.page_title USING utf8mb4) as page_title,
                        p.page_namespace,
                        p.page_is_redirect,
                        p.page_len,
                        CONVERT(r.rev_timestamp USING utf8mb4) as rev_timestamp,
                        CONVERT(a.actor_name USING utf8mb4) as actor_name
                    FROM page p
                    JOIN revision r ON (r.rev_page = p.page_id AND r.rev_parent_id = 0)
                    JOIN actor a ON r.rev_actor = a.actor_id
                    WHERE p.page_namespace = 0
                      AND (CONVERT(p.page_title USING utf8mb4) IN :titles OR p.page_title IN :titles)
                """).bindparams(bindparam("titles", expanding=True))
                res = conn.execute(query, {"titles": list(chunk)})
                for row in res:
                    db_title = row.page_title
                    orig_title = title_map.get(db_title, title_map.get(db_title.replace("_", " "), db_title.replace("_", " ")))
                    ts_str = row.rev_timestamp
                    wiki_date = None
                    iso_str = None
                    if ts_str:
                        try:
                            wiki_date = datetime.strptime(ts_str, "%Y%m%d%H%M%S")
                            iso_str = wiki_date.strftime("%Y-%m-%dT%H:%M:%SZ")
                        except Exception:
                            pass
                    
                    entry = {
                        "exists": True,
                        "wiki_creator": row.actor_name,
                        "wiki_creation_date": wiki_date,
                        "timestamp_str": iso_str,
                        "page_namespace": int(row.page_namespace) if row.page_namespace is not None else 0,
                        "page_is_redirect": bool(row.page_is_redirect),
                        "page_len": int(row.page_len) if row.page_len is not None else 0
                    }
                    results[orig_title.lower()] = entry
                    results[db_title.lower()] = entry
                    results[db_title.replace("_", " ").lower()] = entry
        logger.info(f"Replica query succeeded: {len(results)}/{len(db_titles)} article keys mapped")
        return results
    except Exception as e:
        logger.error(f"Wiki replica query error, falling back to HTTP API: {e}")
        return None

_global_semaphore = asyncio.Semaphore(15)
_http_client = httpx.AsyncClient(
    timeout=15.0,
    limits=httpx.Limits(max_keepalive_connections=30, max_connections=100)
)

async def validate_articles(payload: ValidationRequestPayload) -> List[ValidationResult]:
    results = []
    titles_to_check = payload.titles
    
    # Try MariaDB replica first
    db_replica_results = query_wiki_replica_batch(titles_to_check)
    if db_replica_results is not None:
        for t in titles_to_check:
            info = db_replica_results.get(t.lower())
            if not info:
                results.append(ValidationResult(title=t, is_valid=False, error="Article does not exist"))
                continue
                
            creator = info.get("wiki_creator")
            wiki_date = info.get("wiki_creation_date")
            timestamp_str = info.get("timestamp_str")
            page_ns = info.get("page_namespace", 0)
            is_redirect = info.get("page_is_redirect", False)
            page_len = info.get("page_len", 0)
            
            if not payload.bypass_rules:
                if payload.rule_mainspace_only and page_ns != 0:
                    results.append(ValidationResult(title=t, is_valid=False, error="Must be in Mainspace (Namespace 0)"))
                    continue
                if payload.rule_no_redirect and is_redirect:
                    results.append(ValidationResult(title=t, is_valid=False, error="Article is a redirect page"))
                    continue
                if payload.min_bytes > 0 and page_len < payload.min_bytes:
                    results.append(ValidationResult(title=t, is_valid=False, error=f"Article size too small ({page_len} B < min {payload.min_bytes} B)"))
                    continue
                
                creator_norm = unicodedata.normalize('NFC', creator or "").replace('_', ' ').strip()
                sub_norm = unicodedata.normalize('NFC', payload.submitter_username or "").replace('_', ' ').strip()
                if payload.rule_must_be_creator and creator_norm != sub_norm:
                    results.append(ValidationResult(title=t, is_valid=False, error=f"Author Mismatch: Creator is '{creator}'"))
                    continue
                
                if wiki_date:
                    wd = wiki_date.replace(tzinfo=None) if hasattr(wiki_date, 'tzinfo') else wiki_date
                    cs = payload.start_date.replace(tzinfo=None) if payload.start_date else None
                    ce = payload.end_date.replace(tzinfo=None) if payload.end_date else None
                    if cs and ce and not (cs <= wd <= ce):
                        results.append(ValidationResult(title=t, is_valid=False, error="Created outside contest timeframe"))
                        continue
                    
            results.append(ValidationResult(title=t, is_valid=True, wiki_creator=creator, wiki_creation_date=timestamp_str))
        return results

    # Fallback to HTTP API
    unique_id = os.urandom(4).hex()
    contact_email = os.getenv("CONTACT_EMAIL", "contact@example.com")
    user_agent_username = quote(str(payload.submitter_username or ""), safe="")
    user_agent = f"WikiArticleContestTool/1.0 (User:{user_agent_username}; ContestCode:{payload.contest_code}; {contact_email}; RequestID:{unique_id})"
    headers = {
        "User-Agent": user_agent,
        "Accept-Encoding": "gzip"
    }
    
    async def fetch_single_http(t: str) -> ValidationResult:
        params = {
            "action": "query",
            "format": "json",
            "titles": t,
            "prop": "revisions|info|pageprops",
            "rvprop": "timestamp|user|size|content",
            "rvlimit": 1,
            "rvdir": "newer",
            "inprop": "url"
        }
        async with _global_semaphore:
            try:
                response = await _http_client.post(MEDIAWIKI_API_URL, data=params, headers=headers)
                response.raise_for_status()
                data = response.json()
                pages = data.get("query", {}).get("pages", {})
                for page_id, page in pages.items():
                    if "missing" in page:
                        return ValidationResult(title=t, is_valid=False, error="Article does not exist")
                        
                    revisions = page.get("revisions", [])
                    if not revisions:
                        return ValidationResult(title=t, is_valid=False, error="No revisions found")
                        
                    first_rev = revisions[0]
                    creator = first_rev.get("user")
                    timestamp_str = first_rev.get("timestamp")
                    page_ns = page.get("ns", 0)
                    is_redirect = "redirect" in page
                    page_size = first_rev.get("size", page.get("length", 0))
                    pageprops = page.get("pageprops", {})
                    is_disambig = "disambiguation" in pageprops
                    content = first_rev.get("*") or first_rev.get("slots", {}).get("main", {}).get("*", "")
                    word_count = len([w for w in content.split() if w.strip()]) if content else 0
                    ref_count = len(re.findall(r'<ref[\s/>]', content, re.IGNORECASE)) if content else 0
                    
                    if not payload.bypass_rules:
                        if payload.rule_mainspace_only and page_ns != 0:
                            return ValidationResult(title=t, is_valid=False, error="Must be in Mainspace (Namespace 0)")
                        if payload.rule_no_redirect and is_redirect:
                            return ValidationResult(title=t, is_valid=False, error="Article is a redirect page")
                        if payload.rule_no_disambig and is_disambig:
                            return ValidationResult(title=t, is_valid=False, error="Article is a disambiguation page")
                        if payload.min_bytes > 0 and page_size < payload.min_bytes:
                            return ValidationResult(title=t, is_valid=False, error=f"Article size too small ({page_size} B < min {payload.min_bytes} B)")
                        if payload.min_words > 0 and word_count < payload.min_words:
                            return ValidationResult(title=t, is_valid=False, error=f"Word count too low ({word_count} < min {payload.min_words} words)")
                        if payload.min_refs > 0 and ref_count < payload.min_refs:
                            return ValidationResult(title=t, is_valid=False, error=f"Insufficient references ({ref_count} < min {payload.min_refs} refs)")
                        
                        creator_norm = unicodedata.normalize('NFC', creator or "").replace('_', ' ').strip()
                        sub_norm = unicodedata.normalize('NFC', payload.submitter_username or "").replace('_', ' ').strip()
                        if payload.rule_must_be_creator and creator_norm != sub_norm:
                            return ValidationResult(title=t, is_valid=False, error=f"Author Mismatch: Creator is '{creator}'")
                            
                        creation_time = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=None)
                        start = payload.start_date.replace(tzinfo=None) if payload.start_date else None
                        end = payload.end_date.replace(tzinfo=None) if payload.end_date else None
                        if start and end and not (start <= creation_time <= end):
                            return ValidationResult(title=t, is_valid=False, error="Created outside contest timeframe")
                            
                    return ValidationResult(title=t, is_valid=True, wiki_creator=creator, wiki_creation_date=timestamp_str)
                return ValidationResult(title=t, is_valid=False, error="Article does not exist")
            except Exception as e:
                logger.error(f"HTTP fetch failed for {t}: {e}")
                return ValidationResult(title=t, is_valid=False, error=f"API Error: {str(e)}")

    http_results = await asyncio.gather(*(fetch_single_http(t) for t in titles_to_check))
    results.extend(http_results)
    return results

async def close_parser_client():
    await _http_client.aclose()
