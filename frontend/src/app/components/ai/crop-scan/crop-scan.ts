import { CommonModule } from '@angular/common';
import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  ElementRef,
  OnDestroy,
  OnInit,
  ViewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { Farm } from '../../../models/farm.model';
import { ApiService, CropScanResponse } from '../../../services/api.service';
import { FarmService } from '../../../services/farm.service';

@Component({
  selector: 'app-crop-scan',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './crop-scan.html',
  styleUrl: './crop-scan.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CropScan implements OnInit, OnDestroy {
  @ViewChild('cameraVideo') cameraVideo?: ElementRef<HTMLVideoElement>;
  @ViewChild('captureCanvas') captureCanvas?: ElementRef<HTMLCanvasElement>;

  farms: Farm[] = [];
  selectedFarmId = '';
  cropType = '';
  selectedFile: File | null = null;
  selectedFileName = '';
  selectedFileSource: 'file' | 'camera' | '' = '';
  cameraSupported = false;
  cameraActive = false;
  cameraError = '';
  capturedImagePreviewUrl = '';
  mediaStream: MediaStream | null = null;
  loadingFarms = false;
  scanning = false;
  loadingHistory = false;
  errorMessage = '';
  successMessage = '';
  result: CropScanResponse | null = null;
  resultImageUrl = '';
  resultImageLoading = false;
  resultImageUnavailable = false;
  history: CropScanResponse[] = [];
  private destroy$ = new Subject<void>();
  private pendingCameraFile: File | null = null;

  constructor(
    private readonly api: ApiService,
    private readonly farmService: FarmService,
    private readonly route: ActivatedRoute,
    private readonly cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.cameraSupported = typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia;
    this.selectedFarmId = this.route.snapshot.queryParamMap.get('farm_id') || '';
    this.cropType = this.route.snapshot.queryParamMap.get('crop_type') || '';
    this.loadFarms();
    this.loadScanHistory();
  }

  ngOnDestroy(): void {
    this.resetCameraState();
    this.revokeResultImageUrl();
    this.destroy$.next();
    this.destroy$.complete();
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] || null;
    this.resetCameraState();
    this.setSelectedFile(file, file ? 'file' : '');
    this.cdr.markForCheck();
  }

  async startCamera(): Promise<void> {
    this.errorMessage = '';
    this.successMessage = '';
    this.cameraError = '';
    this.pendingCameraFile = null;
    this.revokeCapturedImagePreviewUrl();

    if (!this.cameraSupported) {
      this.cameraError = 'Camera capture is not available in this browser. You can still choose an image file.';
      this.cdr.markForCheck();
      return;
    }

    this.stopCameraStream();
    this.cameraActive = true;
    this.cdr.detectChanges();

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' } },
      });
      this.mediaStream = stream;

      if (this.cameraVideo?.nativeElement) {
        this.cameraVideo.nativeElement.srcObject = stream;
        await this.cameraVideo.nativeElement.play().catch(() => undefined);
      }
    } catch {
      this.stopCameraStream();
      this.cameraActive = false;
      this.cameraError = 'Unable to open the camera. Please allow camera access or choose an image file instead.';
    }

    this.cdr.markForCheck();
  }

  async capturePhoto(): Promise<void> {
    const video = this.cameraVideo?.nativeElement;
    const canvas = this.captureCanvas?.nativeElement;

    if (!video || !canvas || !video.videoWidth || !video.videoHeight) {
      this.cameraError = 'Camera preview is not ready yet. Please try again in a moment.';
      this.cdr.markForCheck();
      return;
    }

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext('2d');
    if (!context) {
      this.cameraError = 'Unable to capture this photo. Please choose an image file instead.';
      this.cdr.markForCheck();
      return;
    }

    context.drawImage(video, 0, 0, canvas.width, canvas.height);

    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, 'image/jpeg', 0.9);
    });

    if (!blob) {
      this.cameraError = 'Unable to save this camera frame. Please try again or choose an image file.';
      this.cdr.markForCheck();
      return;
    }

    this.revokeCapturedImagePreviewUrl();
    this.pendingCameraFile = new File([blob], `crop-scan-camera-${Date.now()}.jpg`, {
      type: 'image/jpeg',
    });
    this.capturedImagePreviewUrl = URL.createObjectURL(this.pendingCameraFile);
    this.cameraActive = false;
    this.stopCameraStream();
    this.cdr.markForCheck();
  }

  retakePhoto(): void {
    this.revokeCapturedImagePreviewUrl();
    this.pendingCameraFile = null;
    void this.startCamera();
  }

  cancelCamera(): void {
    this.resetCameraState();
    this.cdr.markForCheck();
  }

  useCapturedPhoto(): void {
    if (!this.pendingCameraFile) {
      this.cameraError = 'Capture a photo before using it for the scan.';
      this.cdr.markForCheck();
      return;
    }

    this.setSelectedFile(this.pendingCameraFile, 'camera');
    this.resetCameraState();
    this.cdr.markForCheck();
  }

  submitScan(): void {
    if (!this.selectedFile) {
      this.errorMessage = 'Choose a crop or leaf image before starting the scan.';
      this.cdr.markForCheck();
      return;
    }

    const formData = new FormData();
    formData.append('image', this.selectedFile);
    if (this.selectedFarmId) {
      formData.append('farm_id', this.selectedFarmId);
    }
    if (this.cropType.trim()) {
      formData.append('crop_type', this.cropType.trim());
    }

    this.scanning = true;
    this.errorMessage = '';
    this.successMessage = '';
    this.result = null;
    this.resultImageLoading = false;
    this.resultImageUnavailable = false;
    this.revokeResultImageUrl();
    this.cdr.markForCheck();

    this.api.scanCropHealth(formData)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (scan) => {
          this.result = scan;
          this.history = [scan, ...this.history.filter((item) => item.scan_id !== scan.scan_id)];
          this.successMessage = 'Crop scan completed and saved.';
          this.scanning = false;
          this.loadResultImage(scan);
          this.cdr.markForCheck();
        },
        error: (error) => {
          this.errorMessage =
            this.api.getErrorMessage(error) || 'Unable to scan this image. Please try another crop image.';
          this.scanning = false;
          this.cdr.markForCheck();
        },
      });
  }

  confidencePercent(scan: CropScanResponse): string {
    if (scan.confidence === null || scan.confidence === undefined) {
      return 'Not final';
    }
    return `${Math.round(scan.confidence * 100)}%`;
  }

  predictionConfidencePercent(confidence: number): string {
    return `${confidence > 1 ? Math.round(confidence) : Math.round(confidence * 100)}%`;
  }

  isUncertainScan(scan: CropScanResponse | null = this.result): boolean {
    if (!scan) {
      return false;
    }
    return (
      scan.ai_mode === 'custom_trained_model_uncertain' ||
      scan.model_mode === 'custom_trained_model_uncertain' ||
      scan.label === 'Uncertain crop disease diagnosis' ||
      scan.diagnosis === 'Uncertain crop disease diagnosis'
    );
  }

  scanModeBadge(): string {
    const mode = this.result?.ai_mode || this.result?.model_mode || '';
    if (mode === 'custom_trained_model' || mode === 'custom_trained_model_uncertain') {
      return 'Custom AI';
    }
    if (mode === 'simulated_ai') {
      return 'Simulated AI';
    }
    return 'AI Scan';
  }

  advicePreview(items?: string[], fallback = 'Not provided'): string {
    return items && items.length > 0 ? items[0] : fallback;
  }

  historySummary(scan: CropScanResponse): string {
    return (
      scan.immediate_actions?.[0] ||
      scan.recommendation ||
      scan.monitoring_advice ||
      'Review the full scan advice for next steps.'
    );
  }

  farmName(farmId?: string | null): string {
    if (!farmId) {
      return 'No farm selected';
    }

    const farm = this.farms.find((item) => (item._id || item.id) === farmId);
    return farm?.farm_name || farm?.name || farmId;
  }

  selectedImageStatus(): string {
    if (!this.selectedFileName) {
      return 'JPG, PNG, or WebP up to 5 MB.';
    }

    if (this.selectedFileSource === 'camera') {
      return `Selected camera photo: ${this.selectedFileName}`;
    }

    return `Selected file: ${this.selectedFileName}`;
  }

  private loadResultImage(scan: CropScanResponse): void {
    if (!scan.has_image) {
      this.resultImageUnavailable = true;
      this.cdr.markForCheck();
      return;
    }

    this.resultImageLoading = true;
    this.resultImageUnavailable = false;
    this.api.getCropScanImage(scan.scan_id)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (imageBlob) => {
          this.revokeResultImageUrl();
          this.resultImageUrl = URL.createObjectURL(imageBlob);
          this.resultImageLoading = false;
          this.cdr.markForCheck();
        },
        error: () => {
          this.revokeResultImageUrl();
          this.resultImageLoading = false;
          this.resultImageUnavailable = true;
          this.cdr.markForCheck();
        },
      });
  }

  private revokeResultImageUrl(): void {
    if (this.resultImageUrl) {
      URL.revokeObjectURL(this.resultImageUrl);
      this.resultImageUrl = '';
    }
  }

  private setSelectedFile(file: File | null, source: 'file' | 'camera' | '' = ''): void {
    this.errorMessage = '';
    this.selectedFile = file;
    this.selectedFileName = file?.name || '';
    this.selectedFileSource = file ? source : '';

    if (file && file.size > 5 * 1024 * 1024) {
      this.errorMessage = 'Please choose an image smaller than 5 MB.';
      this.selectedFile = null;
      this.selectedFileName = '';
      this.selectedFileSource = '';
    }
  }

  private resetCameraState(): void {
    this.stopCameraStream();
    this.revokeCapturedImagePreviewUrl();
    this.cameraActive = false;
    this.cameraError = '';
    this.pendingCameraFile = null;
  }

  private stopCameraStream(): void {
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }

    if (this.cameraVideo?.nativeElement) {
      this.cameraVideo.nativeElement.srcObject = null;
    }
  }

  private revokeCapturedImagePreviewUrl(): void {
    if (this.capturedImagePreviewUrl) {
      URL.revokeObjectURL(this.capturedImagePreviewUrl);
      this.capturedImagePreviewUrl = '';
    }
  }

  private loadFarms(): void {
    this.loadingFarms = true;
    this.farmService.getMyFarms(1, 100)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response) => {
          this.farms = response.data;
          if (!this.cropType && this.selectedFarmId) {
            const selectedFarm = this.farms.find((farm) => (farm._id || farm.id) === this.selectedFarmId);
            this.cropType = selectedFarm?.crop_type || '';
          }
          this.loadingFarms = false;
          this.cdr.markForCheck();
        },
        error: () => {
          this.loadingFarms = false;
          this.cdr.markForCheck();
        },
      });
  }

  private loadScanHistory(): void {
    this.loadingHistory = true;
    this.api.getCropScans()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response) => {
          this.history = response.scans || [];
          this.loadingHistory = false;
          this.cdr.markForCheck();
        },
        error: () => {
          this.loadingHistory = false;
          this.cdr.markForCheck();
        },
      });
  }
}
