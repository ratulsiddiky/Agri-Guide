import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { firstValueFrom } from 'rxjs';
import { provideHttpClient } from '@angular/common/http';

import { ApiService, FarmListResponse } from './api.service';

describe('ApiService', () => {
  let service: ApiService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(ApiService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should prefer backend error messages when present', () => {
    expect(
      service.getErrorMessage({ error: { message: 'Backend validation failed' } })
    ).toBe('Backend validation failed');
  });

  it('should map HTTP statuses to reusable error messages', () => {
    expect(service.getErrorMessage({ status: 401 })).toBe(
      'You are not signed in or your session has expired. Please log in again.'
    );
    expect(service.getErrorMessage({ status: 404 })).toBe(
      'The requested farm record could not be found.'
    );
    expect(service.getErrorMessage({ status: 500 })).toBe(
      'The server was unable to complete the farm request. Please try again later.'
    );
  });

  it('should request paginated farms via getFarms and return API response', async () => {
    const expectedResponse: FarmListResponse = {
      data: [
        {
          _id: 'farm-123',
          farm_name: 'North Acre',
          crop_type: 'Wheat',
          address: { area_name: 'Yorkshire', postcode: 'YO1 1AA' },
          location: 'POINT(-1.08 53.96)',
          sensors: [],
          weather_logs: [],
          alerts_history: [],
        },
      ],
      pagination: {
        page: 2,
        limit: 9,
        total: 24,
        has_next: true,
      },
    };

    const responsePromise = firstValueFrom(service.getFarms(2, 9));

    const request = httpMock.expectOne(
      'http://127.0.0.1:5001/api/farms?page=2&limit=9'
    );
    expect(request.request.method).toBe('GET');

    request.flush(expectedResponse);

    const response = await responsePromise;
    expect(response).toEqual(expectedResponse);
  });

  it('should POST createFarm payload to the farms endpoint', async () => {
    const payload = {
      farm_name: 'Green Valley',
      crop_type: 'Corn',
    };

    const responsePromise = firstValueFrom(service.createFarm(payload));

    const request = httpMock.expectOne('http://127.0.0.1:5001/api/farms');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual(payload);

    request.flush({ message: 'Farm registered successfully!', farm_id: 'farm-999' });

    const response = await responsePromise;
    expect(response).toEqual({
      message: 'Farm registered successfully!',
      farm_id: 'farm-999',
    });
  });

  it('should DELETE a farm by id', async () => {
    const responsePromise = firstValueFrom(service.deleteFarm('farm-321'));

    const request = httpMock.expectOne('http://127.0.0.1:5001/api/farms/farm-321');
    expect(request.request.method).toBe('DELETE');

    request.flush(null);

    const response = await responsePromise;
    expect(response).toBeNull();
  });
});
