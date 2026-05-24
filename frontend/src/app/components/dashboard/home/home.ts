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

  readonly kpiCards = [
    { label: 'Total Farms', value: this.totalFarms, detail: 'Currently tracked', tone: 'green' },
    { label: 'Active Alerts', value: '2', detail: 'Needs attention', tone: 'amber' },
    { label: 'Total Sensors', value: '12', detail: 'Across all farms', tone: 'blue' },
    { label: 'Avg Soil Moisture', value: '58.4%', detail: 'Optimal range', tone: 'teal' },
    { label: "Today's Forecast", value: '21°C', detail: 'Partly Cloudy', tone: 'sky' },
  ];

  readonly smartFeatureCards = [
    {
      title: 'System Health',
      accent: 'green',
      metrics: [
        { label: 'API Status', value: 'Online' },
        { label: 'Database', value: 'Connected' },
        { label: 'Target Latency', value: '< 500 ms' },
      ],
    },
    {
      title: 'Latest Sensor Readings',
      accent: 'blue',
      metrics: [
        { label: 'Temperature', value: '23.5°C' },
        { label: 'Humidity', value: '64%' },
        { label: 'Soil Moisture', value: '58.4%' },
        { label: 'Light', value: '42,000 lux' },
      ],
    },
    {
      title: 'Irrigation Decision',
      accent: 'teal',
      metrics: [
        { label: 'Decision', value: 'No irrigation required' },
        { label: 'Reason', value: 'Soil moisture is currently optimal' },
      ],
    },
    {
      title: 'AI Crop Detection',
      accent: 'lime',
      metrics: [
        { label: 'Mode', value: 'Simulated AI' },
        { label: 'Result', value: 'Healthy Leaf' },
        { label: 'Confidence', value: '91%' },
        { label: 'Recommendation', value: 'Continue normal monitoring' },
      ],
    },
    {
      title: 'Weather Alert',
      accent: 'amber',
      metrics: [
        { label: 'Level', value: 'Medium' },
        { label: 'Message', value: 'High temperature expected later today' },
        { label: 'Action', value: 'Monitor soil moisture more frequently' },
      ],
    },
    {
      title: 'Failover Test',
      accent: 'slate',
      metrics: [
        { label: 'Sensor Status', value: 'Offline simulation' },
        { label: 'Mode', value: 'Interpolated reading' },
        { label: 'Confidence', value: 'Medium' },
      ],
    },
  ];

  readonly sensorRows = [
    { sensor: 'SM-204', farm: 'North Field', type: 'Soil Moisture', value: '58.4%', status: 'Optimal' },
    { sensor: 'TMP-118', farm: 'Greenhouse A', type: 'Temperature', value: '23.5°C', status: 'Normal' },
    { sensor: 'HUM-072', farm: 'East Orchard', type: 'Humidity', value: '64%', status: 'Normal' },
    { sensor: 'LUX-331', farm: 'South Plot', type: 'Light', value: '42,000 lux', status: 'High' },
  ];

  get greetingName(): string {
    const user = this.authService.currentUserSignal();
    return user?.username || 'Farmer';
  }

  get dashboardKpiCards() {
    return this.kpiCards.map((card) =>
      card.label === 'Total Farms'
        ? { ...card, value: this.isLoadingStats ? '...' : this.totalFarms }
        : card
    );
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
