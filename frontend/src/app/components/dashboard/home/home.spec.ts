import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { Home } from './home';

import { provideRouter } from '@angular/router';
import { AuthService } from '../../../services/auth.service';
import { ApiService } from '../../../services/api.service';

describe('Home', () => {
  let component: Home;
  let fixture: ComponentFixture<Home>;

  beforeEach(async () => {
    const authServiceStub = {
      currentUserSignal: () => ({
        username: 'farmer-1',
        display_name: 'Farmer One',
        role: 'user',
        token: 'x',
      }),
    } as unknown as AuthService;

    const apiServiceStub = {
      getDashboardSummary: () =>
        of({
          total_farms: 1,
          total_sensors: 5,
          average_soil_moisture: 58,
          latest_temperature: 22,
          latest_humidity: 64,
          active_alerts_count: 0,
          irrigation_recommendation: 'No irrigation required',
          sensor_rows: [],
        }),
      getSystemMetrics: () => of(null),
      getLatestSensors: () => of(null),
      detectCropDisease: () => of(null),
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
});
