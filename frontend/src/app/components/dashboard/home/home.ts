import { Component, OnInit, OnDestroy, ChangeDetectionStrategy, ChangeDetectorRef, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { forkJoin, of, Subject } from 'rxjs';
import { catchError, takeUntil } from 'rxjs/operators';
import { AuthService } from '../../../services/auth.service';
import {
  ApiService,
  DashboardSummaryResponse,
  FailoverTestResponse,
  SystemMetricsResponse,
} from '../../../services/api.service';

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
  apiService = inject(ApiService);
  private cdr = inject(ChangeDetectorRef);

  totalFarms = 0;
  isLoadingStats = true;
  private dashboardLocationSource: DashboardSummaryResponse['location_source'] | null = null;
  private dashboardTimezone: string | null = null;
  private destroy$ = new Subject<void>();

  kpiCards = [
    { label: 'Total Farms', value: this.totalFarms, detail: 'Currently tracked', tone: 'green' },
    { label: 'Active Alerts', value: '...', detail: 'Needs attention', tone: 'amber' },
    { label: 'Total Sensors', value: '...', detail: 'Across all farms', tone: 'blue' },
    { label: 'Avg Soil Moisture', value: '...', detail: 'Awaiting readings', tone: 'teal' },
    { label: "Today's Forecast", value: '...', detail: 'Awaiting synced weather', tone: 'sky' },
  ];

  smartFeatureCards = [
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
        { label: 'Temperature', value: 'No reading' },
        { label: 'Humidity', value: 'No reading' },
        { label: 'Soil Moisture', value: 'No reading' },
        { label: 'Source', value: 'No readings yet' },
      ],
    },
    {
      title: 'Irrigation Decision',
      accent: 'teal',
      metrics: [
        { label: 'Decision', value: 'Awaiting soil moisture data' },
        { label: 'Reason', value: 'No readings yet' },
      ],
    },
    {
      title: 'AI Crop Detection',
      accent: 'lime',
      metrics: [
        { label: 'Mode', value: 'No scan yet' },
        { label: 'Result', value: 'No scans yet' },
        { label: 'Confidence', value: 'N/A' },
        { label: 'Recommendation', value: 'Upload a crop image to get AI guidance.' },
      ],
    },
    {
      title: 'Weather Alert',
      accent: 'amber',
      metrics: [
        { label: 'Level', value: 'None' },
        { label: 'Message', value: 'No synced weather available yet' },
        { label: 'Action', value: 'Sync weather from a farm detail page to see current alerts.' },
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

  sensorRows: DashboardSummaryResponse['sensor_rows'] = [];

  get greetingName(): string {
    const user = this.authService.currentUserSignal();
    return user?.display_name || user?.username || 'Farmer';
  }

  get greetingMessage(): string {
    return this.getGreetingForHour(this.getCurrentHour());
  }

  get locationContextNote(): string {
    if (this.dashboardLocationSource === 'manual_coordinates' || this.dashboardLocationSource === 'browser_geolocation') {
      return 'Using exact farm coordinates';
    }
    if (this.dashboardLocationSource === 'approximate_demo_location') {
      return 'Using approximate demo coordinates';
    }
    return 'Using your device timezone';
  }

  getGreetingForHour(hour: number): string {
    if (hour >= 5 && hour < 12) {
      return 'Good morning';
    }
    if (hour >= 12 && hour < 17) {
      return 'Good afternoon';
    }
    if (hour >= 17 && hour < 22) {
      return 'Good evening';
    }
    return 'Good night';
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

    this.loadSmartAgricultureData();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  private loadSmartAgricultureData(): void {
    forkJoin({
      summary: this.apiService.getDashboardSummary().pipe(
        catchError((err) => {
          console.error('Dashboard summary load failed', err);
          return of(null as DashboardSummaryResponse | null);
        })
      ),
      system: this.apiService.getSystemMetrics().pipe(
        catchError((err) => {
          console.error('System metrics load failed', err);
          return of(null as SystemMetricsResponse | null);
        })
      ),
      failover: this.apiService.getFailoverTest().pipe(
        catchError((err) => {
          console.error('Failover test load failed', err);
          return of(null as FailoverTestResponse | null);
        })
      ),
    })
      .pipe(takeUntil(this.destroy$))
      .subscribe((responses) => {
        this.applyDashboardSummary(responses.summary);
        this.applySystemMetrics(responses.system);
        this.applyFailoverTest(responses.failover);
        this.cdr.markForCheck();
      });
  }

  private updateFeatureCard(title: string, metrics: { label: string; value: string }[]): void {
    this.smartFeatureCards = this.smartFeatureCards.map((card) =>
      card.title === title ? { ...card, metrics } : card
    );
  }

  private updateKpiCard(label: string, value: string, detail: string): void {
    this.kpiCards = this.kpiCards.map((card) =>
      card.label === label ? { ...card, value, detail } : card
    );
  }

  private applySystemMetrics(system: SystemMetricsResponse | null): void {
    if (!system) {
      return;
    }

    this.updateFeatureCard('System Health', [
      { label: 'API Status', value: system.api_status },
      { label: 'Database', value: system.database_status },
      { label: 'Target Latency', value: `< ${system.target_latency_ms} ms` },
    ]);
  }

  private applyDashboardSummary(summary: DashboardSummaryResponse | null): void {
    this.isLoadingStats = false;
    if (!summary) {
      this.totalFarms = 0;
      this.dashboardLocationSource = null;
      this.dashboardTimezone = null;
      return;
    }

    this.dashboardLocationSource = summary.location_source ?? null;
    this.dashboardTimezone = summary.timezone ?? null;
    this.totalFarms = summary.total_farms;
    this.updateKpiCard('Total Farms', `${summary.total_farms}`, 'Your farms');
    this.updateKpiCard('Total Sensors', `${summary.total_sensors}`, 'Across your farms');
    this.updateKpiCard('Active Alerts', `${summary.active_alerts_count}`, 'From your farms');

    const soilValue = summary.average_soil_moisture;
    this.updateKpiCard(
      'Avg Soil Moisture',
      soilValue === null ? 'N/A' : `${soilValue}%`,
      soilValue === null ? 'Add soil sensors' : 'Your farm average'
    );

    this.updateKpiCard(
      "Today's Forecast",
      this.formatNumberWithUnit(summary.weather?.temperature_c ?? summary.latest_temperature, '°C'),
      summary.weather?.condition_summary || 'Latest farm temperature'
    );

    const sensorReadings = summary.latest_sensor_readings;
    this.updateFeatureCard('Latest Sensor Readings', [
      {
        label: 'Temperature',
        value: this.formatNumberWithUnit(sensorReadings?.temperature_c ?? null, '°C', 'No reading'),
      },
      {
        label: 'Humidity',
        value: this.formatNumberWithUnit(sensorReadings?.humidity_percent ?? summary.latest_humidity, '%', 'No reading'),
      },
      {
        label: 'Soil Moisture',
        value: this.formatNumberWithUnit(sensorReadings?.soil_moisture_percent ?? soilValue, '%', 'No reading'),
      },
      {
        label: 'Light',
        value: this.formatNumberWithUnit(sensorReadings?.light_lux ?? null, ' lux', 'No reading'),
      },
    ]);

    const irrigation = summary.irrigation_decision;
    this.updateFeatureCard('Irrigation Decision', [
      { label: 'Decision', value: irrigation?.decision ?? summary.irrigation_recommendation },
      { label: 'Reason', value: irrigation?.reason ?? 'Average soil moisture' },
      { label: 'Priority', value: irrigation?.priority ?? 'low' },
    ]);

    const aiScan = summary.ai_crop_detection;
    this.updateFeatureCard('AI Crop Detection', [
      { label: 'Mode', value: this.formatAiMode(aiScan) },
      { label: 'Result', value: aiScan?.label ?? 'No scans yet' },
      { label: 'Confidence', value: this.formatConfidence(aiScan?.confidence ?? null) },
      { label: 'Recommendation', value: aiScan?.recommendation ?? 'Upload a crop image to get AI guidance.' },
    ]);

    const weatherAlert = summary.weather_alert;
    this.updateFeatureCard('Weather Alert', [
      { label: 'Level', value: weatherAlert?.level ?? 'None' },
      { label: 'Message', value: weatherAlert?.message ?? 'No synced weather available yet' },
      {
        label: 'Action',
        value: weatherAlert?.recommended_action ?? 'Sync weather from a farm detail page to see current alerts.',
      },
    ]);

    if (summary.sensor_rows.length > 0) {
      this.sensorRows = summary.sensor_rows;
    } else {
      this.sensorRows = [];
    }
  }

  private getCurrentHour(): number {
    if (this.dashboardTimezone) {
      try {
        const formatter = new Intl.DateTimeFormat('en-GB', {
          hour: '2-digit',
          hour12: false,
          timeZone: this.dashboardTimezone,
        });
        const hour = Number.parseInt(formatter.format(new Date()), 10);
        if (Number.isFinite(hour)) {
          return hour;
        }
      } catch (error) {
        console.warn('Unable to parse dashboard timezone, using device timezone instead.', error);
      }
    }

    return new Date().getHours();
  }

  private applyFailoverTest(failover: FailoverTestResponse | null): void {
    if (!failover) {
      return;
    }

    this.updateFeatureCard('Failover Test', [
      { label: 'Sensor Status', value: failover.sensor_status },
      { label: 'Mode', value: failover.failover_mode },
      { label: 'Confidence', value: failover.confidence },
    ]);
  }

  private formatNumberWithUnit(value: number | null | undefined, unit: string, fallback = 'N/A'): string {
    if (value === null || value === undefined || Number.isNaN(value)) {
      return fallback;
    }
    const displayValue = unit.trim() === 'lux' ? value.toLocaleString() : value;
    return `${displayValue}${unit}`;
  }

  private formatConfidence(value: number | null): string {
    if (value === null || value === undefined || Number.isNaN(value)) {
      return 'N/A';
    }
    return `${Math.round(value * 100)}%`;
  }

  private formatAiMode(aiScan: DashboardSummaryResponse['ai_crop_detection'] | undefined): string {
    if (!aiScan || aiScan.data_source === 'fallback_demo') {
      return 'No scan yet';
    }
    const mode = aiScan.ai_mode || aiScan.model_mode || aiScan.mode;
    if (mode === 'custom_trained_model' || mode === 'custom_trained_model_uncertain') {
      return 'Custom AI';
    }
    if (mode === 'simulated_ai') {
      return 'Simulated AI';
    }
    return aiScan.mode || 'No scan yet';
  }
}
