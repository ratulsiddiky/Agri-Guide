import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { AuthService } from '../services/auth.service';

export const authInterceptor: HttpInterceptorFn = (req, next) => {

  const authService = inject(AuthService);

  const isAuthRequest =
    req.url.includes('/login') ||
    req.url.includes('/users/register') ||
    req.url.includes('/users/signup') ||
    req.url.includes('/users/verify-email') ||
    req.url.includes('/users/verify') ||
    req.url.includes('/users/resend-verification');

  if (isAuthRequest) {
    return next(req);
  }


  const token = authService.getToken();

  if (!token) {
    return next(req);
  }

  const clonedRequest = req.clone({
    setHeaders: {
      Authorization: `Bearer ${token}`,
    },
  });

  return next(clonedRequest);
};
