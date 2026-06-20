import { Component, OnDestroy, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink, RouterOutlet } from '@angular/router';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { AuthService } from './services/auth.service';
import { GlobalAlert } from './components/shared/global-alert/global-alert';
import { User } from './models/user.model';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, CommonModule, GlobalAlert],
  templateUrl: './app.html',
  styleUrl: './app.css',
})

export class AppComponent implements OnDestroy {
  title = 'smart-agri-guide-frontend';
  profileImageUrl = '';
  private loadedProfileImageKey = '';
  private readonly destroy$ = new Subject<void>();

  constructor(
    public auth: AuthService,
    private readonly router: Router
  ) {
    effect(() => {
      this.loadNavbarProfileImage(this.auth.currentUserSignal());
    });
  }

  ngOnDestroy(): void {
    this.revokeProfileImageUrl();
    this.destroy$.next();
    this.destroy$.complete();
  }

  logout() {
    this.auth.logout().subscribe({
      next: () => void this.router.navigate(['/login']),
      error: () => {
        this.auth.clearSession();
        void this.router.navigate(['/login']);
      },
    });
  }

  navbarInitials(): string {
    return this.initialsForName(this.auth.getDisplayName());
  }

  private loadNavbarProfileImage(user: User | null): void {
    if (!user?.token) {
      this.loadedProfileImageKey = '';
      this.revokeProfileImageUrl();
      return;
    }

    const userKey = user._id || user.user_id || user.username;
    const imageKey = `${userKey}:${user.has_profile_image ? 'image' : 'fallback'}`;
    if (this.loadedProfileImageKey === imageKey) {
      return;
    }

    this.loadedProfileImageKey = imageKey;
    this.revokeProfileImageUrl();

    if (user.has_profile_image === false) {
      return;
    }

    this.auth.getProfileImage()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (imageBlob) => {
          this.revokeProfileImageUrl();
          this.profileImageUrl = URL.createObjectURL(imageBlob);
        },
        error: () => {
          this.revokeProfileImageUrl();
        },
      });
  }

  private initialsForName(name: string): string {
    const parts = name
      .trim()
      .split(/\s+/)
      .filter(Boolean);
    if (parts.length === 0) {
      return 'U';
    }
    if (parts.length === 1) {
      return parts[0].charAt(0).toUpperCase() || 'U';
    }
    return `${parts[0].charAt(0)}${parts[parts.length - 1].charAt(0)}`.toUpperCase();
  }

  private revokeProfileImageUrl(): void {
    if (this.profileImageUrl) {
      URL.revokeObjectURL(this.profileImageUrl);
      this.profileImageUrl = '';
    }
  }
}
