import { ChangeDetectionStrategy, ChangeDetectorRef, Component, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { AuthService } from '../../../services/auth.service';

@Component({
  selector: 'app-verify-email',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './verify-email.html',
  styleUrl: './verify-email.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class VerifyEmail implements OnInit, OnDestroy {
  loading = true;
  successMessage = '';
  errorMessage = '';
  private readonly destroy$ = new Subject<void>();

  constructor(
    private readonly route: ActivatedRoute,
    private readonly authService: AuthService,
    private readonly cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    const token = this.route.snapshot.queryParamMap.get('token')?.trim();

    if (!token) {
      this.loading = false;
      this.errorMessage = 'Verification link is missing a token.';
      this.cdr.markForCheck();
      return;
    }

    this.authService
      .verifyEmailToken(token)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response) => {
          this.loading = false;
          this.successMessage = response.message || 'Email verified successfully. You can now log in.';
          this.authService.emailVerifiedSuccessfully.set(true);
          this.cdr.markForCheck();
        },
        error: (err: unknown) => {
          const errorPayload = err as { error?: { message?: string } };
          this.loading = false;
          this.errorMessage =
            errorPayload.error?.message || 'We could not verify this email link.';
          this.cdr.markForCheck();
        },
      });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }
}
