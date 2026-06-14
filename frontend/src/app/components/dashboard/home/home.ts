import { Component, OnInit, OnDestroy, ChangeDetectionStrategy, ChangeDetectorRef, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { forkJoin, of, Subject } from 'rxjs';
import { catchError, takeUntil } from 'rxjs/operators';
import { AuthService } from '../../../services/auth.service';
import {
  ApiService,
  CropDetectionResponse,
  DashboardSummaryResponse,
  FailoverTestResponse,
  IrrigationDecisionResponse,
  LatestSensorsResponse,
  SystemMetricsResponse,
  WeatherAlertResponse,
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
  private hasUserSummary = false;
  private destroy$ = new Subject<void>();

  kpiCards = [
    { label: 'Total Farms', value: this.totalFarms, detail: 'Currently tracked', tone: 'green' },
    { label: 'Active Alerts', value: '2', detail: 'Needs attention', tone: 'amber' },
    { label: 'Total Sensors', value: '12', detail: 'Across all farms', tone: 'blue' },
    { label: 'Avg Soil Moisture', value: '58.4%', detail: 'Optimal range', tone: 'teal' },
    { label: "Today's Forecast", value: '21°C', detail: 'Partly Cloudy', tone: 'sky' },
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

  sensorRows = [
    { sensor: 'SM-204', farm: 'North Field', type: 'Soil Moisture', value: '58.4%', status: 'Optimal' },
    { sensor: 'TMP-118', farm: 'Greenhouse A', type: 'Temperature', value: '23.5°C', status: 'Normal' },
    { sensor: 'HUM-072', farm: 'East Orchard', type: 'Humidity', value: '64%', status: 'Normal' },
    { sensor: 'LUX-331', farm: 'South Plot', type: 'Light', value: '42,000 lux', status: 'High' },
  ];

  get greetingName(): string {
    const user = this.authService.currentUserSignal();
    return user?.display_name || user?.username || 'Farmer';
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
      sensors: this.apiService.getLatestSensors().pipe(
        catchError((err) => {
          console.error('Latest sensors load failed', err);
          return of(null as LatestSensorsResponse | null);
        })
      ),
      detection: this.apiService.detectCropDisease().pipe(
        catchError((err) => {
          console.error('Crop detection load failed', err);
          return of(null as CropDetectionResponse | null);
        })
      ),
      irrigation: this.apiService.getIrrigationDecision().pipe(
        catchError((err) => {
          console.error('Irrigation decision load failed', err);
          return of(null as IrrigationDecisionResponse | null);
        })
      ),
      weather: this.apiService.getWeatherAlert().pipe(
        catchError((err) => {
          console.error('Weather alert load failed', err);
          return of(null as WeatherAlertResponse | null);
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
        this.applyLatestSensors(responses.sensors);
        this.applyCropDetection(responses.detection);
        this.applyIrrigationDecision(responses.irrigation);
        this.applyWeatherAlert(responses.weather);
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
      return;
    }

    this.hasUserSummary = true;
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
      summary.latest_temperature === null ? 'N/A' : `${summary.latest_temperature}°C`,
      'Latest farm temperature'
    );

    this.updateFeatureCard('Latest Sensor Readings', [
      {
        label: 'Temperature',
        value: summary.latest_temperature === null ? 'No reading' : `${summary.latest_temperature}°C`,
      },
      {
        label: 'Humidity',
        value: summary.latest_humidity === null ? 'No reading' : `${summary.latest_humidity}%`,
      },
      {
        label: 'Soil Moisture',
        value: soilValue === null ? 'No reading' : `${soilValue}%`,
      },
      { label: 'Source', value: 'Your farms' },
    ]);

    this.updateFeatureCard('Irrigation Decision', [
      { label: 'Decision', value: summary.irrigation_recommendation },
      { label: 'Basis', value: 'Average soil moisture' },
    ]);

    if (summary.sensor_rows.length > 0) {
      this.sensorRows = summary.sensor_rows;
    } else {
      this.sensorRows = [];
    }
  }

  private applyLatestSensors(sensors: LatestSensorsResponse | null): void {
    if (!sensors) {
      return;
    }

    if (this.hasUserSummary) {
      return;
    }

    this.updateFeatureCard('Latest Sensor Readings', [
      { label: 'Temperature', value: `${sensors.temperature_c}°C` },
      { label: 'Humidity', value: `${sensors.humidity_percent}%` },
      { label: 'Soil Moisture', value: `${sensors.soil_moisture_percent}%` },
      { label: 'Light', value: `${sensors.light_lux.toLocaleString()} lux` },
    ]);

    this.updateKpiCard('Avg Soil Moisture', `${sensors.soil_moisture_percent}%`, sensors.status);
    this.updateKpiCard("Today's Forecast", `${sensors.temperature_c}°C`, 'Current sensor temperature');

    this.sensorRows = [
      {
        sensor: 'TMP-LIVE',
        farm: sensors.farm_id,
        type: 'Temperature',
        value: `${sensors.temperature_c}°C`,
        status: sensors.status,
      },
      {
        sensor: 'HUM-LIVE',
        farm: sensors.farm_id,
        type: 'Humidity',
        value: `${sensors.humidity_percent}%`,
        status: sensors.status,
      },
      {
        sensor: 'SM-LIVE',
        farm: sensors.farm_id,
        type: 'Soil Moisture',
        value: `${sensors.soil_moisture_percent}%`,
        status: sensors.status,
      },
      {
        sensor: 'LUX-LIVE',
        farm: sensors.farm_id,
        type: 'Light',
        value: `${sensors.light_lux.toLocaleString()} lux`,
        status: sensors.source,
      },
    ];
  }

  private applyIrrigationDecision(irrigation: IrrigationDecisionResponse | null): void {
    if (!irrigation) {
      return;
    }

    if (this.hasUserSummary) {
      return;
    }

    this.updateFeatureCard('Irrigation Decision', [
      { label: 'Decision', value: irrigation.decision },
      { label: 'Reason', value: irrigation.rule_used },
      { label: 'Action', value: irrigation.recommended_action },
    ]);
  }

  private applyCropDetection(detection: CropDetectionResponse | null): void {
    if (!detection) {
      return;
    }

    this.updateFeatureCard('AI Crop Detection', [
      { label: 'Mode', value: detection.mode },
      { label: 'Result', value: detection.prediction.label },
      { label: 'Confidence', value: `${Math.round(detection.prediction.confidence * 100)}%` },
      { label: 'Recommendation', value: detection.prediction.recommendation },
    ]);
  }

  private applyWeatherAlert(weather: WeatherAlertResponse | null): void {
    if (!weather) {
      return;
    }

    this.updateFeatureCard('Weather Alert', [
      { label: 'Level', value: weather.alert_level },
      { label: 'Message', value: weather.message },
      { label: 'Action', value: weather.recommended_action },
    ]);

    if (!this.hasUserSummary) {
      this.updateKpiCard('Active Alerts', weather.alert_level === 'Medium' ? '2' : '1', weather.message);
    }
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
}
