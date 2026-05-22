import { Routes } from '@angular/router';
import { guestGuard, guestMatchGuard } from './guards/auth.guard';

export const authRoutes: Routes = [
  {
    path: 'login',
    canMatch: [guestMatchGuard],
    canActivate: [guestGuard],
    loadComponent: () =>
      import('./components/auth/login/login').then((m) => m.Login),
  },
  {
    path: 'register',
    canMatch: [guestMatchGuard],
    canActivate: [guestGuard],
    loadComponent: () =>
      import('./components/auth/register/register').then((m) => m.Register),
  },
];
