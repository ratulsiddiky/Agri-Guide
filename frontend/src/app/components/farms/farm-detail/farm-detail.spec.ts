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
