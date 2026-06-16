import { ChangeDetectionStrategy, ChangeDetectorRef, Component, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { AuthService } from '../../../services/auth.service';

@Component({
  selector: 'app-forgot-password',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: './forgot-password.html',
  styleUrl: './forgot-password.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ForgotPassword implements OnDestroy {
  readonly forgotPasswordForm = new FormGroup({
    identifier: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required],
    }),
  });

  loading = false;
  successMessage = '';
  errorMessage = '';
  private readonly destroy$ = new Subject<void>();

  constructor(
    private readonly authService: AuthService,
    private readonly cdr: ChangeDetectorRef
  ) {}

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  onSubmit(): void {
    if (this.forgotPasswordForm.invalid) {
      this.forgotPasswordForm.markAllAsTouched();
      this.errorMessage = 'Enter your email or username.';
      return;
    }

    const identifier = this.forgotPasswordForm.controls.identifier.value.trim();
    if (!identifier) {
      this.errorMessage = 'Enter your email or username.';
      return;
    }

    this.loading = true;
    this.successMessage = '';
    this.errorMessage = '';
    this.forgotPasswordForm.disable();

    this.authService
      .forgotPassword(identifier)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response) => {
          this.loading = false;
          this.forgotPasswordForm.enable();
          this.successMessage =
            response.message || 'If an Agri Guide account exists, a password reset email has been sent.';
          this.cdr.markForCheck();
        },
        error: (err: unknown) => {
          const errorPayload = err as { error?: { message?: string } };
          this.loading = false;
          this.forgotPasswordForm.enable();
          this.errorMessage =
            errorPayload.error?.message || 'Unable to request a password reset right now.';
          this.cdr.markForCheck();
        },
      });
  }
}
