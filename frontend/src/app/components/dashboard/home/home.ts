import { Component, OnInit, OnDestroy, ChangeDetectionStrategy, ChangeDetectorRef, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { AuthService } from '../../../services/auth.service';
import { FarmService } from '../../../services/farm.service';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [RouterLink, CommonModule],
  templateUrl: './home.html',
  styleUrls: ['./home.css'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Home implements OnInit, OnDestroy {
  authService = inject(AuthService);
  farmService = inject(FarmService);
  private cdr = inject(ChangeDetectorRef);

  totalFarms = 0;
  isLoadingStats = true;
  private destroy$ = new Subject<void>();

  get greetingName(): string {
    const user = this.authService.currentUserSignal();
    return user?.username || 'Farmer';
  }

  ngOnInit() {
    this.isLoadingStats = true;
    this.cdr.markForCheck();
    
    this.farmService.getFarms(1, 1)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (res) => {
          this.totalFarms = res.pagination?.total || 0;
          this.isLoadingStats = false;
          this.cdr.markForCheck();
        },
        error: (err) => {
          console.error('Stats load failed', err);
          this.totalFarms = 0;
          this.isLoadingStats = false;
          this.cdr.markForCheck();
        }
      });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }
}