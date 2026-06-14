import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { Observable, of, throwError } from 'rxjs';
import { ApiService, CropScanResponse } from '../../../services/api.service';

import { CropScanDetail } from './crop-scan-detail';

describe('CropScanDetail', () => {
  let fixture: ComponentFixture<CropScanDetail>;
  let component: CropScanDetail;
  let apiServiceStub: {
    getCropScan: () => Observable<CropScanResponse>;
    getErrorMessage: (error: any) => string;
  };

  const scan: CropScanResponse = {
    scan_id: 'scan-1',
    farm_id: 'farm-1',
    farm_name: 'North Field',
    crop_type: 'Tomato',
    model_mode: 'simulated_ai',
    model_type: 'crop_leaf_health_classifier',
    future_upgrade_model: 'MobileNetV2 transfer learning CNN',
    label: 'Early Blight Risk',
    confidence: 0.86,
    severity: 'medium',
    recommendation: 'Improve airflow around plants.',
    prevention_steps: ['Avoid overhead watering.'],
    latency_ms: 123,
    image_metadata: {
      filename: 'leaf.png',
      content_type: 'image/png',
      width: 1,
      height: 1,
      format: 'PNG',
    },
    possible_causes: ['Fungal pressure'],
    immediate_actions: ['Remove affected leaves'],
    prevention_plan: ['Rotate crops'],
    monitoring_advice: 'Inspect again in 48 hours.',
    advisory_disclaimer: 'Advisory support only.',
    created_at: '2026-06-14T10:00:00Z',
    timestamp: '2026-06-14T10:00:00Z',
  };

  async function createComponent() {
    await TestBed.configureTestingModule({
      imports: [CropScanDetail],
      providers: [
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: {
              paramMap: {
                get: () => 'scan-1',
              },
            },
          },
        },
        { provide: ApiService, useValue: apiServiceStub },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(CropScanDetail);
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
  }

  beforeEach(() => {
    apiServiceStub = {
      getCropScan: () => of(scan),
      getErrorMessage: (error: any) => error?.error?.message || '',
    };
  });

  it('should render loaded scan recommendations', async () => {
    await createComponent();

    const compiled = fixture.nativeElement as HTMLElement;
    expect(component.scan?.label).toBe('Early Blight Risk');
    expect(compiled.textContent).toContain('Improve airflow around plants.');
    expect(compiled.textContent).toContain('Fungal pressure');
    expect(compiled.textContent).toContain('Remove affected leaves');
  });

  it('should show the no-image-preview MVP note', async () => {
    await createComponent();

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain(
      'Image preview is not stored in this MVP; only scan metadata and diagnosis are saved.'
    );
  });

  it('should show backend error message on load failure', async () => {
    apiServiceStub.getCropScan = () =>
      throwError(() => ({ error: { message: 'Scan not found.' } }));

    await createComponent();

    expect(component.errorMessage).toBe('Scan not found.');
  });
});
