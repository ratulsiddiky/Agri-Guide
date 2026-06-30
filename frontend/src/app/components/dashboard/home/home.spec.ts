import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';

import { Home } from './home';

import { provideRouter } from '@angular/router';
import { AuthService } from '../../../services/auth.service';
import { ApiService } from '../../../services/api.service';

describe('Home', () => {
  let component: Home;
  let fixture: ComponentFixture<Home>;
  let detectCropDiseaseCalls: number;
  let dashboardSummaryCalls: number;
  let syncWeatherCalledWith = '';
  let syncWeatherShouldFail = false;

  beforeEach(async () => {
    const authServiceStub = {
      currentUserSignal: () => ({
        username: 'farmer-1',
        display_name: 'Farmer One',
        role: 'user',
        token: 'x',
      }),
    } as unknown as AuthService;

    detectCropDiseaseCalls = 0;
    dashboardSummaryCalls = 0;
    syncWeatherCalledWith = '';
    syncWeatherShouldFail = false;
    const apiServiceStub = {
      getDashboardSummary: () => {
        dashboardSummaryCalls += 1;
        return of({
          total_farms: 1,
          total_sensors: 5,
          average_soil_moisture: 58,
          latest_temperature: 18.7,
          latest_humidity: 64,
          active_alerts_count: 0,
          irrigation_recommendation: 'No irrigation required',
          primary_farm_id: 'farm-1',
          sensor_rows: [
            {
              sensor: 'lux-demo',
              farm: 'Weather Farm',
              type: 'light',
              value: '34,599 lux',
              status: 'active',
              source: 'auto_generated_demo_sensor',
              source_label: 'Demo sensor',
              last_updated: '2026-06-01T10:00:00Z',
            },
          ],
          weather: {
            farm_id: 'farm-1',
            farm_name: 'Weather Farm',
            temperature_c: 18.7,
            humidity_percent: 72,
            wind_speed_kmh: 14.2,
            precipitation_mm: 0.1,
            rain_mm: 0,
            condition_summary: 'Partly cloudy',
            timestamp: '2026-06-01T10:00:00+00:00',
            data_source: 'latest_weather_log',
          },
          latest_sensor_readings: {
            temperature_c: 23.5,
            humidity_percent: 64,
            soil_moisture_percent: 58,
            light_lux: 42000,
            data_source: 'latest_sensor_reading',
          },
          ai_crop_detection: {
            scan_id: 'scan-1',
            mode: 'custom_trained_model',
            model_mode: 'custom_trained_model',
            ai_mode: 'custom_trained_model',
            label: 'Tomato early blight',
            confidence: 0.968,
            severity: 'medium',
            recommendation: 'Remove affected lower leaves.',
            summary: 'The image is most consistent with tomato early blight.',
            created_at: '2026-06-01T10:00:00+00:00',
            data_source: 'latest_ai_scan',
          },
          weather_alert: {
            level: 'Low',
            message: 'Partly cloudy',
            recommended_action: 'Continue routine monitoring.',
            data_source: 'latest_weather_log',
          },
          irrigation_decision: {
            decision: 'No irrigation required',
            reason: 'Average soil moisture is in range at 58%.',
            recommended_action: 'No irrigation required',
            priority: 'low',
            soil_moisture_percent: 58,
            data_source: 'latest_sensor_reading',
          },
        });
      },
      syncWeather: (id: string) => {
        syncWeatherCalledWith = id;
        return syncWeatherShouldFail
          ? throwError(() => ({ status: 504, error: { message: '' } }))
          : of(void 0);
      },
      getSystemMetrics: () => of(null),
      getLatestSensors: () => of(null),
      detectCropDisease: () => {
        detectCropDiseaseCalls += 1;
        return of(null);
      },
      getIrrigationDecision: () => of(null),
      getWeatherAlert: () => of(null),
      getFailoverTest: () => of(null),
    } as unknown as ApiService;

    await TestBed.configureTestingModule({
      imports: [Home],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: authServiceStub },
        { provide: ApiService, useValue: apiServiceStub },
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(Home);
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should prefer display name in the greeting', () => {
    expect(component.greetingName).toBe('Farmer One');
  });

  it('should map greeting by hour ranges', () => {
    expect(component.getGreetingForHour(5)).toBe('Good morning');
    expect(component.getGreetingForHour(11)).toBe('Good morning');
    expect(component.getGreetingForHour(12)).toBe('Good afternoon');
    expect(component.getGreetingForHour(16)).toBe('Good afternoon');
    expect(component.getGreetingForHour(17)).toBe('Good evening');
    expect(component.getGreetingForHour(21)).toBe('Good evening');
    expect(component.getGreetingForHour(22)).toBe('Good night');
    expect(component.getGreetingForHour(4)).toBe('Good night');
  });

  it('should show exact farm coordinates context for exact location source', () => {
    (component as any).dashboardLocationSource = 'manual_coordinates';
    expect(component.locationContextNote).toBe('Using exact farm coordinates');
  });

  it('should show approximate demo context for demo location source', () => {
    (component as any).dashboardLocationSource = 'approximate_demo_location';
    expect(component.locationContextNote).toBe('Using approximate demo coordinates');
  });

  it('should default to device timezone context when no source is provided', () => {
    (component as any).dashboardLocationSource = null;
    expect(component.locationContextNote).toBe('Using your device timezone');
  });

  it('should render synced weather in today forecast', () => {
    const forecast = component.dashboardKpiCards.find((card) => card.label === "Today's Forecast");

    expect(forecast?.value).toBe('18.7°C');
    expect(forecast?.detail).toBe('Partly cloudy · Synced weather');
  });

  it('should render latest custom AI scan instead of simulated detection data', () => {
    const aiCard = component.smartFeatureCards.find((card) => card.title === 'AI Crop Detection');

    expect(aiCard?.metrics).toEqual([
      { label: 'Mode', value: 'Custom AI' },
      { label: 'Result', value: 'Tomato early blight' },
      { label: 'Model probability', value: '97%' },
      { label: 'Source', value: 'Latest AI scan' },
      { label: 'Recommendation', value: 'Remove affected lower leaves.' },
    ]);
    expect(detectCropDiseaseCalls).toBe(0);
  });

  it('should render a balanced farm health score when enough data is available', () => {
    const healthCard = component.dashboardKpiCards.find((card) => card.label === 'Farm Health Score');

    expect(healthCard?.value).toBe('76/100');
    expect(healthCard?.detail).toBe('Balanced from sensors, alerts, weather, and scans');
  });

  it('should render no scan state from dashboard summary', () => {
    (component as any).applyDashboardSummary({
      total_farms: 1,
      total_sensors: 0,
      average_soil_moisture: null,
      latest_temperature: null,
      latest_humidity: null,
      active_alerts_count: 0,
      irrigation_recommendation: 'Add soil moisture sensors to calculate irrigation guidance.',
      sensor_rows: [],
      ai_crop_detection: {
        scan_id: null,
        mode: 'No scan yet',
        model_mode: null,
        ai_mode: null,
        label: 'No scans yet',
        confidence: null,
        severity: null,
        recommendation: 'Upload a crop image to get AI guidance.',
        summary: '',
        created_at: '',
        data_source: 'fallback_demo',
      },
    });

    const aiCard = component.smartFeatureCards.find((card) => card.title === 'AI Crop Detection');
    expect(aiCard?.metrics[0]).toEqual({ label: 'Mode', value: 'No scan yet' });
    expect(aiCard?.metrics[1]).toEqual({ label: 'Result', value: 'No scans yet' });
    expect(aiCard?.metrics[2]).toEqual({ label: 'Model probability', value: 'N/A' });
    expect(component.dashboardKpiCards.find((card) => card.label === 'Farm Health Score')?.value).toBe('Not enough data yet');
  });

  it('should render recent sensor reading source labels', () => {
    fixture.detectChanges();
    const tableText = fixture.nativeElement.querySelector('.table-card')?.textContent ?? '';

    expect(component.sensorRows[0].value).toBe('34,599 lux');
    expect(component.sensorRows[0].source_label).toBe('Demo sensor');
    expect(tableText).toContain('Source');
    expect(tableText).toContain('Demo sensor');
    expect(tableText).toContain('Last updated');
  });

  it('should sync weather for the primary farm and refresh the dashboard summary', () => {
    component.syncDashboardWeather();

    expect(syncWeatherCalledWith).toBe('farm-1');
    expect(dashboardSummaryCalls).toBe(2);
    expect(component.weatherSyncMessage).toBe('Weather synced. Dashboard updated.');
    expect(component.weatherSyncError).toBe('');
  });

  it('should not sync weather when no primary farm is available', () => {
    component.primaryFarmId = null;

    component.syncDashboardWeather();

    expect(syncWeatherCalledWith).toBe('');
    expect(component.weatherSyncError).toBe('Add a farm to sync weather.');
  });

  it('should show a friendly weather sync error', () => {
    syncWeatherShouldFail = true;

    component.syncDashboardWeather();

    expect(syncWeatherCalledWith).toBe('farm-1');
    expect(component.weatherSyncError).toBe(
      'The server was unable to complete the farm request. Please try again later.'
    );
  });
});
