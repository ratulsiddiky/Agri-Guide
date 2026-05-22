import { Component, OnInit, OnDestroy, ChangeDetectionStrategy, ChangeDetectorRef, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { Subject } from 'rxjs';
import { finalize, takeUntil } from 'rxjs/operators';
import { FarmService } from '../../../services/farm.service';
import { BroadcastAlertRequest } from '../../../services/api.service';
import { AuthService } from '../../../services/auth.service';

@Component({
  selector: 'app-admin-dashboard',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './admin-dashboard.html',
  styleUrl: './admin-dashboard.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AdminDashboard implements OnInit, OnDestroy {
  readonly authService = inject(AuthService);
  private readonly cdr = inject(ChangeDetectorRef);

  readonly broadcastForm = new FormGroup({
    alert_type: new FormControl('Flood', {
      nonNullable: true,
      validators: [Validators.required],
    }),
    danger_zone: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required],
    }),
  });

  readonly insightsForm = new FormGroup({
    region_name: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required],
    }),
  });

  alertLoading = false;
  insightsLoading = false;
  alertMessage = '';
  alertError = '';
  insightsError = '';
  farmsNotified = 0;
  totalFarmsTracked = 0;
  statsLoading = true;
  insightsData: { community_avg_temp: number; total_farms_included: number } | null =
    null;
  
  private destroy$ = new Subject<void>();

  constructor(private readonly farmService: FarmService) {}

  get greetingName(): string {
    const user = this.authService.currentUserSignal();

    if (!user) {
      return 'Admin';
    }

    if ((user.role || '').toLowerCase() === 'admin') {
      return 'Admin';
    }

    return user.username || 'Admin';
  }

  ngOnInit(): void {
    this.loadQuickStats();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  private setBroadcastLoading(isLoading: boolean): void {
    this.alertLoading = isLoading;
    this.cdr.markForCheck();

    if (isLoading) {
      this.broadcastForm.disable({ emitEvent: false });
      return;
    }

    this.broadcastForm.enable({ emitEvent: false });
  }

  private setInsightsLoading(isLoading: boolean): void {
    this.insightsLoading = isLoading;
    this.cdr.markForCheck();

    if (isLoading) {
      this.insightsForm.disable({ emitEvent: false });
      return;
    }

    this.insightsForm.enable({ emitEvent: false });
  }

  private loadQuickStats(): void {
    this.statsLoading = true;
    this.cdr.markForCheck();

    this.farmService.getFarms(1, 1)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response) => {
          this.totalFarmsTracked =
            response.pagination?.total ?? response.data?.length ?? 0;
          this.statsLoading = false;
          this.cdr.markForCheck();
        },
        error: () => {
          this.totalFarmsTracked = 0;
          this.statsLoading = false;
          this.cdr.markForCheck();
        },
      });
  }

  private getErrorMessage(error: unknown, fallback: string): string {
    const backendMessage = (error as { error?: { message?: unknown } } | null)?.error
      ?.message;

    return typeof backendMessage === 'string' && backendMessage.trim()
      ? backendMessage
      : fallback;
  }


  onBroadcast(): void {
    if (this.broadcastForm.invalid) {
      this.broadcastForm.markAllAsTouched();
      this.cdr.markForCheck();
      return;
    }

    this.setBroadcastLoading(true);
    this.alertMessage = '';
    this.alertError = '';

    const rawZone = this.broadcastForm.controls.danger_zone.value.trim();
    const parsedZone = this.parseDangerZone(rawZone);

    if (!parsedZone) {
      this.setBroadcastLoading(false);
      this.alertError =
        'danger_zone must be valid GeoJSON Polygon JSON with coordinates.';
      this.cdr.markForCheck();
      return;
    }

    const payload: BroadcastAlertRequest = {
      alert_type: this.broadcastForm.controls.alert_type.value,
      danger_zone: parsedZone,
    };

    this.farmService
      .broadcastAlert(payload)
      .pipe(
        takeUntil(this.destroy$),
        finalize(() => this.setBroadcastLoading(false))
      )
      .subscribe({
        next: (response) => {
          this.farmsNotified = response.farms_notified;
          this.alertMessage = response.message || 'Alert broadcast successful.';
          this.cdr.markForCheck();
        },
        error: (err) => {
          this.alertError = this.getErrorMessage(
            err,
            'Alert broadcast failed. The request timed out or the server could not process the GeoJSON polygon.'
          );
          this.cdr.markForCheck();
        },
      });
  }


  loadRegionalInsights(): void {
    if (this.insightsForm.invalid) {
      this.insightsForm.markAllAsTouched();
      this.cdr.markForCheck();
      return;
    }

    this.setInsightsLoading(true);
    this.insightsError = '';
    this.insightsData = null;

    const regionName = this.insightsForm.controls.region_name.value.trim();

    this.farmService
      .getRegionalInsights(regionName)
      .pipe(
        takeUntil(this.destroy$),
        finalize(() => this.setInsightsLoading(false))
      )
      .subscribe({
        next: (response) => {
          this.insightsData = response.data;
          this.cdr.markForCheck();
        },
        error: (err) => {
          this.insightsError = this.getErrorMessage(
            err,
            'Regional insights are unavailable for this region. Please try another area name.'
          );
          this.cdr.markForCheck();
        },
      });
  }


  private parseDangerZone(
    rawJson: string
  ): { type: 'Polygon'; coordinates: number[][][] } | null {
    try {
      const parsed = JSON.parse(rawJson) as {
        type?: string;
        coordinates?: unknown;
      };

      if (
        parsed.type !== 'Polygon' ||
        !Array.isArray(parsed.coordinates) ||
        parsed.coordinates.length === 0
      ) {
        return null;
      }

      return {
        type: 'Polygon',
        coordinates: parsed.coordinates as number[][][],
      };
    } catch {
      return null;
    }
  }
}