import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute } from '@angular/router';
import { provideRouter } from '@angular/router';
import { signal } from '@angular/core';
import { Observable, of, throwError } from 'rxjs';
import { AuthService } from '../../../services/auth.service';

import { VerifyEmail } from './verify-email';

describe('VerifyEmail', () => {
  let fixture: ComponentFixture<VerifyEmail>;

  function setup(verifyEmailToken: () => Observable<unknown>) {
    return TestBed.configureTestingModule({
      imports: [VerifyEmail],
      providers: [
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: {
              queryParamMap: {
                get: (key: string) => (key === 'token' ? 'valid-token' : null),
              },
            },
          },
        },
        {
          provide: AuthService,
          useValue: {
            verifyEmailToken,
            emailVerifiedSuccessfully: signal(false),
          },
        },
      ],
    }).compileComponents();
  }

  it('renders success after verification', async () => {
    await setup(() => of({ message: 'Email verified successfully.' }));

    fixture = TestBed.createComponent(VerifyEmail);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Email verified successfully.');
  });

  it('renders backend errors', async () => {
    await setup(() =>
      throwError(() => ({ error: { message: 'Verification link expired' } }))
    );

    fixture = TestBed.createComponent(VerifyEmail);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Verification link expired');
  });
});
