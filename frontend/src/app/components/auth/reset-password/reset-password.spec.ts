import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute } from '@angular/router';
import { provideRouter } from '@angular/router';
import { Observable, of, throwError } from 'rxjs';
import { AuthService } from '../../../services/auth.service';

import { ResetPassword } from './reset-password';

describe('ResetPassword', () => {
  let fixture: ComponentFixture<ResetPassword>;

  function setup(resetPassword: () => Observable<unknown>, token = 'valid-token') {
    return TestBed.configureTestingModule({
      imports: [ResetPassword],
      providers: [
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: {
              queryParamMap: {
                get: (key: string) => (key === 'token' ? token : null),
              },
            },
          },
        },
        {
          provide: AuthService,
          useValue: { resetPassword },
        },
      ],
    }).compileComponents();
  }

  it('renders success after resetting the password', async () => {
    await setup(() => of({ message: 'Password reset successfully. You can now log in.' }));

    fixture = TestBed.createComponent(ResetPassword);
    fixture.detectChanges();
    fixture.componentInstance.resetPasswordForm.controls.newPassword.setValue('NewPassword123!');
    fixture.componentInstance.resetPasswordForm.controls.confirmPassword.setValue('NewPassword123!');
    fixture.componentInstance.onSubmit();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Password reset successfully');
  });

  it('renders backend errors', async () => {
    await setup(() => throwError(() => ({ error: { message: 'Password reset link expired' } })));

    fixture = TestBed.createComponent(ResetPassword);
    fixture.detectChanges();
    fixture.componentInstance.resetPasswordForm.controls.newPassword.setValue('NewPassword123!');
    fixture.componentInstance.resetPasswordForm.controls.confirmPassword.setValue('NewPassword123!');
    fixture.componentInstance.onSubmit();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Password reset link expired');
  });
});
