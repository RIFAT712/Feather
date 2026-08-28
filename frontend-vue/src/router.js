import { createRouter, createWebHistory } from 'vue-router';
import Home from './views/Home.vue';
const AdminDashboard = () => import('./views/AdminDashboard.vue');
const ContestLayout = () => import('./views/ContestLayout.vue');
const ContestDashboard = () => import('./views/ContestDashboard.vue');
const SubmitArticles = () => import('./views/SubmitArticles.vue');
const ReviewQueue = () => import('./views/ReviewQueue.vue');
const ActivityLog = () => import('./views/ActivityLog.vue');
const JuryStats = () => import('./views/JuryStats.vue');
const UserProfile = () => import('./views/UserProfile.vue');
const GlobalProfile = () => import('./views/GlobalProfile.vue');

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
