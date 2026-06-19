import { Component, OnInit, OnDestroy, ChangeDetectionStrategy, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { ApiService } from '../../../services/api.service';
import { FarmService } from '../../../services/farm.service';
import { NotificationService } from '../../../services/notification.service';
import { Farm, FarmLocationSource } from '../../../models/farm.model';

type FarmLocationPayload = Partial<Farm> & {
  address?: {
    area_name?: string;
    postcode?: string;
  };
};

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
    address_line: new FormControl('', {
      nonNullable: true,
    }),
    city: new FormControl('', {
      nonNullable: true,
    }),
    region: new FormControl('', {
      nonNullable: true,
    }),
    postcode: new FormControl('', {
      nonNullable: true,
    }),
    country: new FormControl('', {
      nonNullable: true,
    }),
    latitude: new FormControl('', {
      nonNullable: true,
    }),
    longitude: new FormControl('', {
      nonNullable: true,
    }),
    location_source: new FormControl<FarmLocationSource | ''>('', {
      nonNullable: true,
    }),
  });

  isEditMode = false;
  farmId = '';
  loading = false;
  loadError = false;
  submitting = false;
  errorMessage = '';
  successMessage = '';
  locationMessage = '';
  locationMessageType: 'success' | 'danger' | 'info' = 'info';
  geolocationLoading = false;
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
    this.loadError = false;
    this.errorMessage = '';
    this.farmForm.disable();
    this.cdr.markForCheck();

    this.farmService.getFarmById(this.farmId)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (farm) => {
          const coordinates = this.extractCoordinates(farm);
          this.farmForm.patchValue({
            farm_name: farm.farm_name || '',
            crop_type: farm.crop_type || '',
            address_line: farm.address_line || '',
            city: farm.city || '',
            region: farm.region || farm.address?.area_name || '',
            postcode: farm.postcode || farm.address?.postcode || '',
            country: farm.country || '',
            latitude: coordinates.latitude,
            longitude: coordinates.longitude,
            location_source: farm.location_source || '',
          });
          this.loading = false;
          this.loadError = false;
          this.farmForm.enable();
          this.cdr.markForCheck();
        },
        error: (err) => {
          this.errorMessage =
            this.apiService.getErrorMessage(err) ||
            `Unable to load farm '${this.farmId}' for editing. Please refresh and try again.`;
          this.loading = false;
          this.loadError = true;
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

    const payload = this.buildPayload();
    if (!payload) {
      this.cdr.markForCheck();
      return;
    }

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

  createFarm(payload: FarmLocationPayload): void {
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

  updateFarm(payload: FarmLocationPayload): void {
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

  useCurrentLocation(): void {
    this.locationMessage = '';
    if (!navigator.geolocation) {
      this.locationMessage = 'Your browser does not support current location. You can enter coordinates manually.';
      this.locationMessageType = 'danger';
      this.cdr.markForCheck();
      return;
    }

    this.geolocationLoading = true;
    this.locationMessage = 'Getting your current location...';
    this.locationMessageType = 'info';
    this.cdr.markForCheck();

    navigator.geolocation.getCurrentPosition(
      (position) => {
        this.farmForm.patchValue(
          {
            latitude: String(Number(position.coords.latitude.toFixed(6))),
            longitude: String(Number(position.coords.longitude.toFixed(6))),
            location_source: 'browser_geolocation',
          },
          { emitEvent: false }
        );
        this.geolocationLoading = false;
        this.locationMessage = 'Current location added. Save the farm to use these exact coordinates.';
        this.locationMessageType = 'success';
        this.cdr.markForCheck();
      },
      () => {
        this.geolocationLoading = false;
        this.locationMessage =
          'We could not access your current location. You can still enter coordinates or an address manually.';
        this.locationMessageType = 'danger';
        this.cdr.markForCheck();
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 60000,
      }
    );
  }

  onManualAddressInput(): void {
    const hasCoordinates = this.hasCoordinateValue();
    if (!hasCoordinates) {
      this.farmForm.controls.location_source.setValue('manual_address');
    }
  }

  onManualCoordinateInput(): void {
    if (this.hasCoordinateValue()) {
      this.farmForm.controls.location_source.setValue('manual_coordinates');
    }
  }

  private extractCoordinates(farm: Farm): { latitude: string; longitude: string } {
    if (farm.latitude !== undefined && farm.longitude !== undefined) {
      return {
        latitude: String(farm.latitude),
        longitude: String(farm.longitude),
      };
    }

    const location = farm.location;
    if (
      typeof location === 'object' &&
      Array.isArray(location.coordinates) &&
      location.coordinates.length === 2
    ) {
      return {
        latitude: String(location.coordinates[1]),
        longitude: String(location.coordinates[0]),
      };
    }

    return { latitude: '', longitude: '' };
  }

  private hasCoordinateValue(): boolean {
    return Boolean(
      this.farmForm.controls.latitude.value.trim() ||
        this.farmForm.controls.longitude.value.trim()
    );
  }

  private buildPayload(): FarmLocationPayload | null {
    const latitudeText = this.farmForm.controls.latitude.value.trim();
    const longitudeText = this.farmForm.controls.longitude.value.trim();
    const hasLatitude = Boolean(latitudeText);
    const hasLongitude = Boolean(longitudeText);

    if (hasLatitude !== hasLongitude) {
      this.locationMessage = 'Latitude and longitude must be provided together.';
      this.locationMessageType = 'danger';
      return null;
    }

    let latitude: number | undefined;
    let longitude: number | undefined;
    if (hasLatitude && hasLongitude) {
      latitude = Number(latitudeText);
      longitude = Number(longitudeText);
      if (Number.isNaN(latitude) || latitude < -90 || latitude > 90) {
        this.locationMessage = 'Latitude must be a number between -90 and 90.';
        this.locationMessageType = 'danger';
        return null;
      }
      if (Number.isNaN(longitude) || longitude < -180 || longitude > 180) {
        this.locationMessage = 'Longitude must be a number between -180 and 180.';
        this.locationMessageType = 'danger';
        return null;
      }
    }

    const addressLine = this.farmForm.controls.address_line.value.trim();
    const city = this.farmForm.controls.city.value.trim();
    const region = this.farmForm.controls.region.value.trim();
    const postcode = this.farmForm.controls.postcode.value.trim();
    const country = this.farmForm.controls.country.value.trim();
    const hasAddress = Boolean(addressLine || city || region || postcode || country);
    const selectedSource = this.farmForm.controls.location_source.value;
    const locationSource: FarmLocationSource | undefined =
      latitude !== undefined && longitude !== undefined
        ? selectedSource === 'browser_geolocation'
          ? 'browser_geolocation'
          : 'manual_coordinates'
        : hasAddress
          ? 'manual_address'
          : undefined;

    this.locationMessage = '';

    return {
      farm_name: this.farmForm.controls.farm_name.value.trim(),
      crop_type: this.farmForm.controls.crop_type.value.trim(),
      address_line: addressLine || undefined,
      city: city || undefined,
      region: region || undefined,
      postcode: postcode || undefined,
      country: country || undefined,
      latitude,
      longitude,
      location_source: locationSource,
      address: {
        area_name: region || undefined,
        postcode: postcode || undefined,
      },
    };
  }
}
