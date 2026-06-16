import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Observable, of, throwError } from 'rxjs';
import { AuthService } from '../../../services/auth.service';

import { ForgotPassword } from './forgot-password';

describe('ForgotPassword', () => {
  let fixture: ComponentFixture<ForgotPassword>;

  function setup(forgotPassword: () => Observable<unknown>) {
    return TestBed.configureTestingModule({
      imports: [ForgotPassword],
      providers: [
        provideRouter([]),
        {
          provide: AuthService,
          useValue: { forgotPassword },
        },
      ],
    }).compileComponents();
  }

  it('renders generic success after requesting a reset link', async () => {
    await setup(() => of({ message: 'If an Agri Guide account exists, a password reset email has been sent.' }));

    fixture = TestBed.createComponent(ForgotPassword);
    fixture.detectChanges();
    fixture.componentInstance.forgotPasswordForm.controls.identifier.setValue('farmer_one');
    fixture.componentInstance.onSubmit();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('password reset email has been sent');
  });

  it('renders backend errors', async () => {
    await setup(() => throwError(() => ({ error: { message: 'Unable to request reset' } })));

    fixture = TestBed.createComponent(ForgotPassword);
    fixture.detectChanges();
    fixture.componentInstance.forgotPasswordForm.controls.identifier.setValue('farmer_one');
    fixture.componentInstance.onSubmit();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Unable to request reset');
  });
});
