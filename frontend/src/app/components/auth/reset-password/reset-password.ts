import { ChangeDetectionStrategy, ChangeDetectorRef, Component, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  AbstractControl,
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { AuthService } from '../../../services/auth.service';

function passwordsMatch(control: AbstractControl): ValidationErrors | null {
  const password = control.get('newPassword')?.value;
  const confirmPassword = control.get('confirmPassword')?.value;
  return password && confirmPassword && password !== confirmPassword
    ? { passwordMismatch: true }
    : null;
}

@Component({
  selector: 'app-reset-password',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: './reset-password.html',
  styleUrl: './reset-password.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ResetPassword implements OnInit, OnDestroy {
  readonly resetPasswordForm = new FormGroup(
    {
      newPassword: new FormControl('', {
        nonNullable: true,
        validators: [Validators.required, Validators.minLength(8)],
      }),
      confirmPassword: new FormControl('', {
        nonNullable: true,
        validators: [Validators.required],
      }),
    },
    { validators: passwordsMatch }
  );

  loading = false;
  successMessage = '';
  errorMessage = '';
  private token = '';
  private readonly destroy$ = new Subject<void>();

  constructor(
    private readonly route: ActivatedRoute,
    private readonly authService: AuthService,
    private readonly cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.token = this.route.snapshot.queryParamMap.get('token')?.trim() || '';
    if (!this.token) {
      this.errorMessage = 'Password reset link is missing a token.';
      this.resetPasswordForm.disable();
      this.cdr.markForCheck();
    }
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  onSubmit(): void {
    if (!this.token) {
      this.errorMessage = 'Password reset link is missing a token.';
      return;
    }

    if (this.resetPasswordForm.invalid) {
      this.resetPasswordForm.markAllAsTouched();
      this.errorMessage = this.resetPasswordForm.hasError('passwordMismatch')
        ? 'Passwords do not match.'
        : 'Enter a valid new password.';
      return;
    }

    this.loading = true;
    this.successMessage = '';
    this.errorMessage = '';
    this.resetPasswordForm.disable();

    this.authService
      .resetPassword(this.token, this.resetPasswordForm.controls.newPassword.value.trim())
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response) => {
          this.loading = false;
          this.successMessage = response.message || 'Password reset successfully. You can now log in.';
          this.cdr.markForCheck();
        },
        error: (err: unknown) => {
          const errorPayload = err as { error?: { message?: string } };
          this.loading = false;
          this.resetPasswordForm.enable();
          this.errorMessage =
            errorPayload.error?.message || 'Unable to reset your password right now.';
          this.cdr.markForCheck();
        },
      });
  }
}
