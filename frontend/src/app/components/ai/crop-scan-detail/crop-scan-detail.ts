import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, ChangeDetectorRef, Component, OnDestroy, OnInit } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { ApiService, CropScanResponse } from '../../../services/api.service';

@Component({
  selector: 'app-crop-scan-detail',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './crop-scan-detail.html',
  styleUrl: './crop-scan-detail.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CropScanDetail implements OnInit, OnDestroy {
  scan: CropScanResponse | null = null;
  imagePreviewUrl = '';
  imagePreviewLoading = false;
  imagePreviewUnavailable = false;
  loading = true;
  errorMessage = '';
  private destroy$ = new Subject<void>();

  constructor(
    private readonly api: ApiService,
    private readonly route: ActivatedRoute,
    private readonly cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    const scanId = this.route.snapshot.paramMap.get('id') || '';
    this.loadScan(scanId);
  }

  ngOnDestroy(): void {
    this.revokeImagePreviewUrl();
    this.destroy$.next();
    this.destroy$.complete();
  }

  confidencePercent(scan: CropScanResponse): string {
    return `${Math.round((scan.confidence || 0) * 100)}%`;
  }

  farmLabel(scan: CropScanResponse): string {
    return scan.farm_name || scan.farm_id || 'No farm selected';
  }

  imageDetails(scan: CropScanResponse): string {
    const metadata = scan.image_metadata || { filename: 'Image' };
    const dimensions =
      metadata.width && metadata.height ? `${metadata.width} x ${metadata.height}` : 'Dimensions not available';
    const format = metadata.format || metadata.content_type || 'Format not available';
    return `${metadata.filename || 'Image'} · ${dimensions} · ${format}`;
  }

  private loadScan(scanId: string): void {
    if (!scanId) {
      this.errorMessage = 'Scan not found.';
      this.loading = false;
      this.cdr.markForCheck();
      return;
    }

    this.loading = true;
    this.errorMessage = '';
    this.imagePreviewLoading = false;
    this.imagePreviewUnavailable = false;
    this.revokeImagePreviewUrl();
    this.api.getCropScan(scanId)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (scan) => {
          this.scan = scan;
          this.loading = false;
          this.loadImagePreview(scan);
          this.cdr.markForCheck();
        },
        error: (error) => {
          this.errorMessage =
            this.api.getErrorMessage(error) || error?.error?.message || 'Unable to load this crop scan.';
          this.loading = false;
          this.cdr.markForCheck();
        },
      });
  }

  private loadImagePreview(scan: CropScanResponse): void {
    if (!scan.has_image) {
      this.imagePreviewUnavailable = true;
      this.cdr.markForCheck();
      return;
    }

    this.imagePreviewLoading = true;
    this.imagePreviewUnavailable = false;
    this.api.getCropScanImage(scan.scan_id)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (imageBlob) => {
          this.revokeImagePreviewUrl();
          this.imagePreviewUrl = URL.createObjectURL(imageBlob);
          this.imagePreviewLoading = false;
          this.cdr.markForCheck();
        },
        error: () => {
          this.revokeImagePreviewUrl();
          this.imagePreviewLoading = false;
          this.imagePreviewUnavailable = true;
          this.cdr.markForCheck();
        },
      });
  }

  private revokeImagePreviewUrl(): void {
    if (this.imagePreviewUrl) {
      URL.revokeObjectURL(this.imagePreviewUrl);
      this.imagePreviewUrl = '';
    }
  }
}
