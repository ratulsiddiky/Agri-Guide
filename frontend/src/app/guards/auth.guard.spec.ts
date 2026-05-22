import { TestBed } from '@angular/core/testing';
import { Router, UrlTree, provideRouter } from '@angular/router';
import { adminGuard } from './auth.guard';
import { AuthService } from '../services/auth.service';

describe('adminGuard', () => {
  let authServiceStub: {
    isAuthenticated: () => boolean;
    getRole: () => string;
  };

  beforeEach(() => {
    authServiceStub = {
      isAuthenticated: () => true,
      getRole: () => 'user',
    };

    TestBed.configureTestingModule({
      providers: [provideRouter([]), { provide: AuthService, useValue: authServiceStub }],
    });
  });

  it('should redirect non-admin users away from /admin to home', () => {
    const result = TestBed.runInInjectionContext(() => adminGuard({} as never, {} as never));
    const router = TestBed.inject(Router);

    expect(result instanceof UrlTree).toBe(true);
    expect(router.serializeUrl(result as UrlTree)).toBe('/');
  });
});
