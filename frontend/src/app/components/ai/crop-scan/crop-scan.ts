import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, ChangeDetectorRef, Component, OnDestroy, OnInit } from '@angular/core';
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
  farms: Farm[] = [];
  selectedFarmId = '';
  cropType = '';
  selectedFile: File | null = null;
  selectedFileName = '';
  loadingFarms = false;
  scanning = false;
  loadingHistory = false;
  errorMessage = '';
  successMessage = '';
  result: CropScanResponse | null = null;
  history: CropScanResponse[] = [];
  private destroy$ = new Subject<void>();

  constructor(
    private readonly api: ApiService,
    private readonly farmService: FarmService,
    private readonly route: ActivatedRoute,
    private readonly cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.selectedFarmId = this.route.snapshot.queryParamMap.get('farm_id') || '';
    this.cropType = this.route.snapshot.queryParamMap.get('crop_type') || '';
    this.loadFarms();
    this.loadScanHistory();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] || null;
    this.errorMessage = '';
    this.selectedFile = file;
    this.selectedFileName = file?.name || '';

    if (file && file.size > 5 * 1024 * 1024) {
      this.errorMessage = 'Please choose an image smaller than 5 MB.';
      this.selectedFile = null;
    }

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
    this.cdr.markForCheck();

    this.api.scanCropHealth(formData)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (scan) => {
          this.result = scan;
          this.history = [scan, ...this.history.filter((item) => item.scan_id !== scan.scan_id)];
          this.successMessage = 'Crop scan completed and saved.';
          this.scanning = false;
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
    return `${Math.round((scan.confidence || 0) * 100)}%`;
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
