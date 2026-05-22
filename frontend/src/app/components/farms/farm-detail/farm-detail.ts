import { Component, OnInit, OnDestroy, ChangeDetectionStrategy, ChangeDetectorRef } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subject, forkJoin, timer } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { Farm, FarmSensor } from '../../../models/farm.model';
import { ApiService } from '../../../services/api.service';
import { FarmService } from '../../../services/farm.service';
import { HighlightStatusDirective } from '../../../directives/highlight-status.directive';

interface FarmInsights {
  average_temp?: number;
  average_wind?: number;
  [key: string]: unknown;
}

interface IrrigationStatus {
  status?: string;
  moisture?: number;
  [key: string]: unknown;
}

@Component({
  selector: 'app-farm-detail',
  standalone: true,
  imports: [CommonModule, RouterLink, FormsModule, HighlightStatusDirective],
  templateUrl: './farm-detail.html',
  styleUrl: './farm-detail.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FarmDetail implements OnInit, OnDestroy {
  farm: Farm | null = null;
  insights: FarmInsights | null = null;
  irrigation: IrrigationStatus | null = null;
  loading = true;
  error = false;
  errorMessage = '';
  syncLoading = false;
  syncMessage = '';
  toastMessage = '';
  toastType: 'success' | 'danger' = 'success';
  showSensorForm = false;
  newSensor: FarmSensor = { sensor_id: '', type: '' };
  sensorMessage = '';
  private destroy$ = new Subject<void>();

  constructor(
    private readonly route: ActivatedRoute,
    private readonly api: ApiService,
    private readonly farmService: FarmService,
    private readonly cdr: ChangeDetectorRef  
  ) {}

  get farmId(): string {
    return this.route.snapshot.paramMap.get('id') || '';
  }

  ngOnInit() {
    if (!this.farmId || this.farmId === 'undefined') {
      this.error = true;
      this.errorMessage =
        'The farm identifier is missing or invalid. Please return to All Farms and try again.';
      this.loading = false;
      this.cdr.markForCheck(); 
      return;
    }
    this.loadFarmData();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  private loadFarmData(): void {
    this.loading = true;
    this.error = false;
    this.errorMessage = '';
    this.cdr.markForCheck(); 

    forkJoin({
      farm: this.farmService.getFarmById(this.farmId),
      insights: this.farmService.getFarmInsights(this.farmId),
      irrigation: this.farmService.checkIrrigation(this.farmId),
    })
    .pipe(takeUntil(this.destroy$))
    .subscribe({
      next: (data) => {
        this.farm = data.farm;
        this.insights = data.insights.dashboard_data as FarmInsights;
        this.irrigation = data.irrigation as IrrigationStatus;
        this.loading = false;
        this.cdr.markForCheck();  
      },
      error: (err) => {
        this.error = true;
        this.errorMessage = this.api.getErrorMessage(err) ||
          `Unable to load farm '${this.farmId}'. Please refresh and try again.`;
        console.error(this.errorMessage);
        this.loading = false;
        this.cdr.markForCheck(); 
      },
    });
  }

  syncWeather() {
    this.syncLoading = true;
    this.syncMessage = '';
    this.cdr.markForCheck(); 
    
    this.farmService.syncWeather(this.farmId)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => {
          this.syncMessage = '✅ Weather synced successfully.';
          this.showToast('Weather synced successfully.', 'success');
          this.syncLoading = false;
          this.cdr.markForCheck(); 
          this.loadFarmData();
        },
        error: (err) => {
          const message =
            this.api.getErrorMessage(err) ||
            `Weather sync failed for farm '${this.farmId}'. Please verify the coordinates and try again.`;
          this.syncMessage = `❌ ${message}`;
          this.showToast(message, 'danger');
          this.syncLoading = false;
          this.cdr.markForCheck();  
        },
      });
  }

  addSensor() {
    if (!this.newSensor.sensor_id || !this.newSensor.type) {
      this.sensorMessage = 'Please fill in both fields.';
      return;
    }
    this.farmService.addSensor(this.farmId, this.newSensor)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => {
          this.sensorMessage = 'Sensor added successfully.';
          this.showSensorForm = false;
          this.newSensor = { sensor_id: '', type: '' };
          this.cdr.markForCheck();  
          this.loadFarmData();
        },
        error: (err) => {
          this.sensorMessage =
            this.api.getErrorMessage(err) ||
            `Unable to add the sensor to farm '${this.farmId}'. Please check the sensor details and try again.`;
          this.cdr.markForCheck(); 
        },
      });
  }

  showToast(message: string, type: 'success' | 'danger'): void {
    this.toastMessage = message;
    this.toastType = type;
    this.cdr.markForCheck();  
    
    timer(2500)
      .pipe(takeUntil(this.destroy$))
      .subscribe(() => {
        this.toastMessage = '';
        this.cdr.markForCheck(); 
      });
  }
}