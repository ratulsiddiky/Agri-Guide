import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';

import { ApiService } from './api.service';
import { FarmService } from './farm.service';

describe('FarmService', () => {
  let service: FarmService;
  let apiServiceStub: any;

  beforeEach(() => {
    apiServiceStub = {
      getFarms: () =>
        of({
          data: [],
          pagination: { page: 1, limit: 9, total: 0, has_next: false },
        }),
      getFarmById: () => of({}),
      searchFarms: () => of({ data: [] }),
      createFarm: () => of({ message: 'ok' }),
      updateFarm: () => of({ message: 'ok' }),
      deleteFarm: () => of(void 0),
      getFarmInsights: () => of({ dashboard_data: {} }),
      checkIrrigation: () => of({ status: 'OK' }),
      syncWeather: () => of(void 0),
      addSensor: () => of(void 0),
      broadcastAlert: () => of({ message: 'ok', farms_notified: 0 }),
      getRegionalInsights: () =>
        of({
          message: 'ok',
          data: { community_avg_temp: 0, total_farms_included: 0 },
        }),
      getErrorMessage: (error: any): string => {
        const msg = error?.error?.message;
        if (typeof msg === 'string' && msg.trim()) return msg;
        if (error?.status === 400) return 'The request could not be completed because the farm data was invalid.';
        if (error?.status === 401) return 'You are not signed in or your session has expired. Please log in again.';
        if (error?.status === 403) return 'You do not have permission to perform this farm action.';
        if (error?.status === 404) return 'The requested farm record could not be found.';
        if (error?.status >= 500) return 'The server was unable to complete the farm request. Please try again later.';
        return '';
      },
    };

    TestBed.configureTestingModule({
      providers: [{ provide: ApiService, useValue: apiServiceStub }],
    });

    service = TestBed.inject(FarmService);
  });

  it('should pass through the backend validation message for a missing farm', async () => {
    apiServiceStub.getFarmById = () =>
      throwError(
        () =>
          new HttpErrorResponse({
            status: 404,
            statusText: 'Not Found',
            error: { message: "No farm was found for id 'farm-1'." },
          })
      );

    await new Promise<void>((resolve, reject) => {
      service.getFarmById('farm-1').subscribe({
        next: () => reject(new Error('Expected the request to fail')),
        error: (err) => {
          expect(err).toBeInstanceOf(HttpErrorResponse);
          expect(err.error.message).toContain("No farm was found for id 'farm-1'.");
          resolve();
        },
      });
    });
  });

  it('should convert a validation failure into a helpful fallback message', async () => {
    apiServiceStub.createFarm = () =>
      throwError(
        () =>
          new HttpErrorResponse({
            status: 400,
            statusText: 'Bad Request',
            error: {},
          })
      );

    await new Promise<void>((resolve, reject) => {
      service.createFarm({ farm_name: '', crop_type: '', address: { area_name: '' } }).subscribe({
        next: () => reject(new Error('Expected the request to fail')),
        error: (err) => {
          expect(err).toBeInstanceOf(HttpErrorResponse);
          expect(err.error.message).toBe(
            'The request could not be completed because the farm data was invalid.'
          );
          resolve();
        },
      });
    });
  });
});
