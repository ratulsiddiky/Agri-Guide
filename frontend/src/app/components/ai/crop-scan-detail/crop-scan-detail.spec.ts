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
    getCropScanImage: () => Observable<Blob>;
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
    label: 'Leaf Blight Risk',
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
    explanation: 'Leaf spots suggest a possible fungal disease risk.',
    severity_explanation: 'Medium severity means the crop should be inspected soon.',
    confidence_explanation: 'The symptom pattern commonly aligns with leaf blight risk.',
    likely_causes: ['Fungal pressure'],
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
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: () => 'blob:mock-scan-image',
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: () => undefined,
    });

    apiServiceStub = {
      getCropScan: () => of(scan),
      getCropScanImage: () => of(new Blob(['preview'], { type: 'image/png' })),
      getErrorMessage: (error: any) => error?.error?.message || '',
    };
  });

  it('should render loaded scan recommendations', async () => {
    await createComponent();

    const compiled = fixture.nativeElement as HTMLElement;
    expect(component.scan?.label).toBe('Leaf Blight Risk');
    expect(compiled.textContent).toContain('Improve airflow around plants.');
    expect(compiled.textContent).toContain('Leaf spots suggest a possible fungal disease risk.');
    expect(compiled.textContent).toContain('Medium severity means the crop should be inspected soon.');
    expect(compiled.textContent).toContain('The symptom pattern commonly aligns with leaf blight risk.');
    expect(compiled.textContent).toContain('Fungal pressure');
    expect(compiled.textContent).toContain('Remove affected leaves');
  });

  it('should show the no-image-preview MVP note', async () => {
    await createComponent();

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('Image preview is not stored for this scan.');
  });

  it('should render image preview when the scan has a stored image', async () => {
    apiServiceStub.getCropScan = () => of({ ...scan, has_image: true });

    await createComponent();

    const compiled = fixture.nativeElement as HTMLElement;
    const image = compiled.querySelector('.scan-preview img') as HTMLImageElement | null;
    expect(image?.getAttribute('src')).toBe('blob:mock-scan-image');
    expect(compiled.textContent).not.toContain('Image preview is not stored for this scan.');
  });

  it('should show backend error message on load failure', async () => {
    apiServiceStub.getCropScan = () =>
      throwError(() => ({ error: { message: 'Scan not found.' } }));

    await createComponent();

    expect(component.errorMessage).toBe('Scan not found.');
  });

  it('should render safe fallbacks for older scans without richer explanation fields', async () => {
    const oldScan = {
      ...scan,
      explanation: undefined,
      severity_explanation: undefined,
      confidence_explanation: undefined,
      likely_causes: undefined,
    };
    apiServiceStub.getCropScan = () => of(oldScan);

    await createComponent();

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain(
      'The scan compares visible crop symptoms with the simulated diagnosis knowledge base.'
    );
    expect(compiled.textContent).toContain('Severity reflects the suggested urgency of field follow-up.');
    expect(compiled.textContent).toContain('Model probability reflects the model assessment of the image.');
    expect(compiled.textContent).toContain('AI-assisted diagnosis, not expert confirmation.');
  });
});
