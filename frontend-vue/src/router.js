import { createRouter, createWebHistory } from 'vue-router';
import Home from './views/Home.vue';
import AdminDashboard from './views/AdminDashboard.vue';
import ContestLayout from './views/ContestLayout.vue';
import ContestDashboard from './views/ContestDashboard.vue';
import SubmitArticles from './views/SubmitArticles.vue';
import ReviewQueue from './views/ReviewQueue.vue';
import ActivityLog from './views/ActivityLog.vue';
import JuryStats from './views/JuryStats.vue';
import UserProfile from './views/UserProfile.vue';
import GlobalProfile from './views/GlobalProfile.vue';

const routes = [
  { path: '/', component: Home },
  { path: '/admin', component: AdminDashboard },
  { path: '/user/:username', component: GlobalProfile },
  { 
    path: '/:code', 
    component: ContestLayout,
    children: [
      { path: '', component: ContestDashboard },
      { path: 'submit', component: SubmitArticles },
      { path: 'jury/review', component: ReviewQueue },
      { path: 'jury/review-v2', component: ReviewQueue, props: { assignedQueue: true } },
      { path: 'jury', component: JuryStats },
      { path: 'progress', component: JuryStats },
      { path: 'log', component: ActivityLog },
      { path: 'result', component: () => import('./views/ContestResult.vue') },
      { path: 'user/:username', component: UserProfile },
      { path: 'config', component: () => import('./views/ContestConfig.vue') }
    ]
  }
];

export default createRouter({
  history: createWebHistory(),
  routes
});
