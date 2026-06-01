import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap } from '@angular/router';
import { of } from 'rxjs';

import { FarmDetail } from './farm-detail';
import { FarmService } from '../../../services/farm.service';

describe('FarmDetail', () => {
  let component: FarmDetail;
  let fixture: ComponentFixture<FarmDetail>;
  let farmServiceSpy: FarmService;
  let syncWeatherCalledWith = '';

  beforeEach(async () => {
    syncWeatherCalledWith = '';
    farmServiceSpy = {
      getFarmById: () =>
        of({ _id: 'farm-1', farm_name: 'North Field', sensors: [] } as never),
      getFarmInsights: () =>
        of({ dashboard_data: { average_temp: 18, average_wind: 6 } } as never),
      checkIrrigation: () => of({ status: 'OK', moisture: 44 } as never),
      getFarmSensors: () => of([] as never),
      getSensorHistory: () =>
        of({
          farm_id: 'farm-1',
          farm_name: 'North Field',
          timestamps: ['2026-06-01T08:00:00+00:00', '2026-06-01T09:00:00+00:00'],
          series: {
            soil_moisture: [44, 46],
            temperature: [20, 21],
            humidity: [60, 62],
          },
          data_source: 'stored_sensor_readings',
        } as never),
      getFarmWeather: () =>
        of({
          farm_id: 'farm-1',
          farm_name: 'North Field',
          latitude: 54.5973,
          longitude: -5.9301,
          location_source: 'stored_coordinates',
          temperature_c: 18,
          humidity_percent: 70,
          wind_speed_kmh: 12,
          precipitation_mm: 0,
          rain_mm: 0,
          weather_code: 2,
          condition_summary: 'Partly cloudy',
          timestamp: '2026-06-01T10:00',
          provider: 'Open-Meteo',
          data_source: 'open_meteo_current_weather',
        } as never),
      generateDemoSensors: () => of({ count: 5, sensors: [] } as never),
      syncWeather: (id: string) => {
        syncWeatherCalledWith = id;
        return of(void 0);
      },
      addSensor: () => of(void 0),
    } as unknown as FarmService;

    await TestBed.configureTestingModule({
      imports: [FarmDetail],
      providers: [
        { provide: FarmService, useValue: farmServiceSpy },
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: {
              paramMap: convertToParamMap({ id: 'farm-1' }),
            },
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(FarmDetail);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should call syncWeather and show success toast', () => {
    component.syncWeather();

    expect(syncWeatherCalledWith).toBe('farm-1');
    expect(component.toastMessage).toBe('Weather synced successfully.');
  });
});
