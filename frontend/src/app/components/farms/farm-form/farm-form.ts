import { Component, OnInit, OnDestroy, ChangeDetectionStrategy, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { ApiService } from '../../../services/api.service';
import { FarmService } from '../../../services/farm.service';
import { NotificationService } from '../../../services/notification.service';

@Component({
  selector: 'app-farm-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: './farm-form.html',
  styleUrl: './farm-form.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FarmForm implements OnInit, OnDestroy {
  readonly farmForm = new FormGroup({
    farm_name: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required],
    }),
    crop_type: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required],
    }),
    area_name: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required],
    }),
  });

  isEditMode = false;
  farmId = '';
  loading = false;
  submitting = false;
  errorMessage = '';
  successMessage = '';
  private destroy$ = new Subject<void>();

  constructor(
    private readonly apiService: ApiService,
    private readonly farmService: FarmService,
    private readonly route: ActivatedRoute,
    private readonly router: Router,
    private readonly notificationService: NotificationService,
    private readonly cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.farmForm.enable();
    this.farmId = this.route.snapshot.paramMap.get('id') || '';
    this.isEditMode = !!this.farmId;
    this.cdr.markForCheck();

    if (this.isEditMode) {
      this.loadFarmForEdit();
    }
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  loadFarmForEdit(): void {
    this.loading = true;
    this.errorMessage = '';
    this.farmForm.disable();
    this.cdr.markForCheck();

    this.farmService.getFarmById(this.farmId)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (farm) => {
          this.farmForm.patchValue({
            farm_name: farm.farm_name || '',
            crop_type: farm.crop_type || '',
            area_name: farm.address?.area_name || '',
          });
          this.loading = false;
          this.farmForm.enable();
          this.cdr.markForCheck();
        },
        error: (err) => {
          this.errorMessage =
            this.apiService.getErrorMessage(err) ||
            `Unable to load farm '${this.farmId}' for editing. Please refresh and try again.`;
          this.loading = false;
          this.farmForm.enable();
          this.cdr.markForCheck();
        },
      });
  }

  onSubmit(): void {
    if (this.farmForm.invalid) {
      this.farmForm.markAllAsTouched();
      this.cdr.markForCheck();
      return;
    }

    const payload = {
      farm_name: this.farmForm.controls.farm_name.value.trim(),
      crop_type: this.farmForm.controls.crop_type.value.trim(),
      address: {
        area_name: this.farmForm.controls.area_name.value.trim(),
      },
    };

    this.submitting = true;
    this.errorMessage = '';
    this.successMessage = '';
    this.farmForm.disable();
    this.cdr.markForCheck();

    if (this.isEditMode) {
      this.updateFarm(payload);
      return;
    }

    this.createFarm(payload);
  }

  createFarm(payload: {
    farm_name: string;
    crop_type: string;
    address: { area_name: string };
  }): void {
    this.farmService.createFarm(payload)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response) => {
          this.successMessage = response.message || 'Farm created successfully.';
          this.notificationService.showSuccess(this.successMessage);
          this.submitting = false;
          this.farmForm.enable();
          this.cdr.markForCheck();
          
          const createdFarmId = response.farm_id;
          setTimeout(() => {
            if (createdFarmId) {
              void this.router.navigate(['/farms', createdFarmId]);
              return;
            }
            void this.router.navigate(['/farms']);
          }, 1500);
        },
        error: (err) => {
          this.errorMessage =
            this.apiService.getErrorMessage(err) ||
            'Unable to create the farm. Please correct the form fields and try again.';
          this.notificationService.showError(this.errorMessage);
          this.submitting = false;
          this.farmForm.enable();
          this.cdr.markForCheck();
        },
      });
  }

  updateFarm(payload: {
    farm_name: string;
    crop_type: string;
    address: { area_name: string };
  }): void {
    this.farmService.updateFarm(this.farmId, payload)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response) => {
          this.successMessage = response.message || 'Farm updated successfully.';
          this.notificationService.showSuccess(this.successMessage);
          this.submitting = false;
          this.farmForm.enable();
          this.cdr.markForCheck();
          
          
          setTimeout(() => {
            void this.router.navigate(['/farms', this.farmId]);
          }, 1500);
        },
        error: (err) => {
          this.errorMessage =
            this.apiService.getErrorMessage(err) ||
            `Unable to update farm '${this.farmId}'. Please review your changes and try again.`;
          this.notificationService.showError(this.errorMessage);
          this.submitting = false;
          this.farmForm.enable();
          this.cdr.markForCheck();
        },
      });
  }
}