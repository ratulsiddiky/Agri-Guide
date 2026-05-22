import { Injectable, signal } from '@angular/core';

export type NotificationType = 'success' | 'error' | 'info';

export interface NotificationState {
  type: NotificationType;
  message: string;
}

@Injectable({
  providedIn: 'root',
})
export class NotificationService {
  private timeoutId: ReturnType<typeof setTimeout> | null = null;
  readonly notification = signal<NotificationState | null>(null);

  /**
   * Shows a success notification and auto-hides it after a short delay.
   */
  showSuccess(message: string): void {
    this.show({ type: 'success', message });
  }

  /**
   * Shows an error notification and auto-hides it after a short delay.
   */
  showError(message: string): void {
    this.show({ type: 'error', message });
  }

  /**
   * Clears the currently visible global notification.
   */
  clear(): void {
    if (this.timeoutId) {
      clearTimeout(this.timeoutId);
      this.timeoutId = null;
    }
    this.notification.set(null);
  }

  /**
   * Pushes a new notification and schedules automatic dismissal.
   */
  private show(state: NotificationState): void {
    if (this.timeoutId) {
      clearTimeout(this.timeoutId);
      this.timeoutId = null;
    }

    this.notification.set(state);

    this.timeoutId = setTimeout(() => {
      this.notification.set(null);
      this.timeoutId = null;
    }, 3500);
  }
}
