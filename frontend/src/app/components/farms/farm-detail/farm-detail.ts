import {
  Component,
  OnInit,
  OnDestroy,
  AfterViewInit,
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  ElementRef,
  ViewChild,
} from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subject, forkJoin, of, timer } from 'rxjs';
import { catchError, takeUntil } from 'rxjs/operators';
import {
  Chart,
  ChartConfiguration,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Farm, FarmSensor } from '../../../models/farm.model';
import { ApiService, FarmWeatherResponse, SensorHistoryResponse } from '../../../services/api.service';
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

interface SensorReadingFormState {
  sensor_type: string;
  value: string;
  unit: string;
  notes: string;
}

const SENSOR_READING_UNITS: Record<string, string> = {
  soil_moisture: '%',
  temperature: '°C',
  humidity: '%',
  light: 'lux',
  ph: 'pH',
};

Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Legend, Filler);

@Component({
  selector: 'app-farm-detail',
  standalone: true,
  imports: [CommonModule, RouterLink, FormsModule, HighlightStatusDirective],
  templateUrl: './farm-detail.html',
  styleUrl: './farm-detail.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FarmDetail implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('soilMoistureChart')
  private soilMoistureChartCanvas?: ElementRef<HTMLCanvasElement>;
  @ViewChild('temperatureChart')
  private temperatureChartCanvas?: ElementRef<HTMLCanvasElement>;
  @ViewChild('humidityChart')
  private humidityChartCanvas?: ElementRef<HTMLCanvasElement>;

  farm: Farm | null = null;
  insights: FarmInsights | null = null;
  irrigation: IrrigationStatus | null = null;
  sensorHistory: SensorHistoryResponse | null = null;
  farmWeather: FarmWeatherResponse | null = null;
  actionPlan: any = null;
  actionPlanLoading = true;
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
  sensorReadingForm: SensorReadingFormState = {
    sensor_type: 'soil_moisture',
    value: '',
    unit: SENSOR_READING_UNITS['soil_moisture'],
    notes: '',
  };
  sensorReadingLoading = false;
  sensorReadingMessage = '';
  generatingDemoSensors = false;
  chartMessage = '';
  private chartsReady = false;
  private sensorCharts: Chart[] = [];
  private chartRenderTimer: number | undefined;
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

  ngAfterViewInit(): void {
    this.chartsReady = true;
    this.scheduleChartRender();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
    if (this.chartRenderTimer !== undefined) {
      window.clearTimeout(this.chartRenderTimer);
    }
    this.destroyCharts();
  }

  private loadFarmData(): void {
    this.loading = true;
    this.actionPlanLoading = true;
    this.error = false;
    this.errorMessage = '';
    this.cdr.markForCheck(); 

    forkJoin({
      farm: this.farmService.getFarmById(this.farmId),
      sensors: this.farmService.getFarmSensors(this.farmId).pipe(
        catchError(() => of([] as FarmSensor[]))
      ),
      insights: this.farmService.getFarmInsights(this.farmId).pipe(
        catchError(() => of(null))
      ),
      irrigation: this.farmService.checkIrrigation(this.farmId).pipe(
        catchError(() => of(null))
      ),
      sensorHistory: this.farmService.getSensorHistory(this.farmId).pipe(
        catchError(() => of(null))
      ),
      weather: this.farmService.getFarmWeather(this.farmId).pipe(
        catchError(() => of(null))
      ),
      actionPlan: this.farmService.getActionPlan(this.farmId).pipe(catchError(() => of(null))),
    })
    .pipe(takeUntil(this.destroy$))
    .subscribe({
      next: (data) => {
        this.farm = { ...data.farm, sensors: data.sensors };
        this.insights = data.insights?.dashboard_data as FarmInsights | null;
        this.irrigation = data.irrigation as IrrigationStatus;
        this.sensorHistory = data.sensorHistory as SensorHistoryResponse | null;
        this.farmWeather = data.weather as FarmWeatherResponse | null;
        this.actionPlan = data.actionPlan || null;
        this.chartMessage = this.sensorHistory?.data_source === 'simulated_from_latest'
          ? 'Showing simulated trend data from current sensor values.'
          : '';
        this.loading = false;
        this.actionPlanLoading = false;
        this.cdr.markForCheck();  
        this.scheduleChartRender();
      },
      error: (err) => {
        this.error = true;
        this.errorMessage = this.api.getErrorMessage(err) ||
          `Unable to load farm '${this.farmId}'. Please refresh and try again.`;
        console.error(this.errorMessage);
        this.loading = false;
        this.actionPlanLoading = false;
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

  onSensorReadingTypeChange(): void {
    this.sensorReadingForm.unit = SENSOR_READING_UNITS[this.sensorReadingForm.sensor_type] || '';
  }

  addSensorReading(): void {
    const numericValue = Number(this.sensorReadingForm.value);
    if (!this.sensorReadingForm.sensor_type || Number.isNaN(numericValue)) {
      this.sensorReadingMessage = 'Please choose a sensor type and enter a numeric value.';
      return;
    }

    this.sensorReadingLoading = true;
    this.sensorReadingMessage = '';
    this.cdr.markForCheck();

    this.farmService
      .addSensorReading(this.farmId, {
        sensor_type: this.sensorReadingForm.sensor_type,
        value: numericValue,
        unit: this.sensorReadingForm.unit,
        notes: this.sensorReadingForm.notes.trim() || undefined,
      })
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response) => {
          this.sensorReadingMessage = `Sensor reading added successfully for ${response.sensor_type}.`;
          this.showToast(this.sensorReadingMessage, 'success');
          this.sensorReadingLoading = false;
          this.sensorReadingForm.value = '';
          this.sensorReadingForm.notes = '';
          this.cdr.markForCheck();
          this.loadFarmData();
        },
        error: (err) => {
          this.sensorReadingMessage =
            this.api.getErrorMessage(err) ||
            `Unable to add the sensor reading to farm '${this.farmId}'. Please check the value and try again.`;
          this.showToast(this.sensorReadingMessage, 'danger');
          this.sensorReadingLoading = false;
          this.cdr.markForCheck();
        },
      });
  }

  generateDemoSensors(): void {
    this.generatingDemoSensors = true;
    this.sensorMessage = '';
    this.cdr.markForCheck();

    this.farmService.generateDemoSensors(this.farmId)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => {
          this.sensorMessage = 'Demo sensors generated successfully.';
          this.showToast('Demo sensors generated successfully.', 'success');
          this.generatingDemoSensors = false;
          this.cdr.markForCheck();
          this.loadFarmData();
        },
        error: (err) => {
          this.sensorMessage =
            this.api.getErrorMessage(err) ||
            `Unable to generate demo sensors for farm '${this.farmId}'. Please try again.`;
          this.showToast(this.sensorMessage, 'danger');
          this.generatingDemoSensors = false;
          this.cdr.markForCheck();
        },
      });
  }

  sensorReading(sensor: FarmSensor): string {
    const value = sensor.value ?? sensor.readings?.[sensor.readings.length - 1]?.value;
    const unit = typeof sensor.unit === 'string' ? sensor.unit : '';

    return value === undefined || value === null ? 'No reading' : `${value}${unit}`;
  }

  weatherValue(value: number | null | undefined, unit: string): string {
    return value === null || value === undefined ? 'N/A' : `${value}${unit}`;
  }

  get weatherSourceLabel(): string {
    if (!this.farmWeather) {
      return '';
    }

    if (this.farmWeather.data_source === 'fallback_simulated_weather') {
      return 'Fallback simulated weather';
    }

    return this.farmWeather.location_source === 'approximate_demo_location'
      ? 'Open-Meteo using approximate demo coordinates'
      : 'Open-Meteo live weather';
  }

  private scheduleChartRender(): void {
    if (!this.chartsReady || !this.sensorHistory) {
      return;
    }

    if (this.chartRenderTimer !== undefined) {
      window.clearTimeout(this.chartRenderTimer);
    }

    this.chartRenderTimer = window.setTimeout(() => this.renderSensorCharts(), 80);
  }

  private renderSensorCharts(): void {
    if (
      !this.sensorHistory ||
      !this.soilMoistureChartCanvas ||
      !this.temperatureChartCanvas ||
      !this.humidityChartCanvas
    ) {
      return;
    }

    this.destroyCharts();
    const labels = this.sensorHistory.timestamps.map((timestamp) =>
      timestamp ? new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''
    );

    this.sensorCharts = [
      this.createLineChart(
        this.soilMoistureChartCanvas.nativeElement,
        'Soil moisture',
        labels,
        this.sensorHistory.series.soil_moisture,
        '#0d9488',
        '%'
      ),
      this.createLineChart(
        this.temperatureChartCanvas.nativeElement,
        'Temperature',
        labels,
        this.sensorHistory.series.temperature,
        '#dc2626',
        '°C'
      ),
      this.createLineChart(
        this.humidityChartCanvas.nativeElement,
        'Humidity',
        labels,
        this.sensorHistory.series.humidity,
        '#2563eb',
        '%'
      ),
    ];
  }

  private createLineChart(
    canvas: HTMLCanvasElement,
    label: string,
    labels: string[],
    values: Array<number | null>,
    color: string,
    unit: string
  ): Chart {
    const config: ChartConfiguration<'line'> = {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label,
            data: values,
            borderColor: color,
            backgroundColor: `${color}22`,
            pointBackgroundColor: color,
            pointRadius: 3,
            tension: 0.35,
            fill: true,
            spanGaps: true,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (context) => `${label}: ${context.parsed.y}${unit}`,
            },
          },
        },
        scales: {
          y: {
            beginAtZero: false,
            ticks: {
              callback: (value) => `${value}${unit}`,
            },
          },
          x: {
            ticks: {
              maxRotation: 0,
              autoSkip: true,
            },
          },
        },
      },
    };

    return new Chart(canvas, config);
  }

  private destroyCharts(): void {
    this.sensorCharts.forEach((chart) => chart.destroy());
    this.sensorCharts = [];
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
