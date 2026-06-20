import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  ElementRef,
  OnDestroy,
  OnInit,
  ViewChild,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { AuthService, UserProfile } from '../../services/auth.service';

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: './profile.html',
  styleUrl: './profile.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Profile implements OnInit, OnDestroy {
  @ViewChild('cameraVideo') cameraVideo?: ElementRef<HTMLVideoElement>;
  @ViewChild('captureCanvas') captureCanvas?: ElementRef<HTMLCanvasElement>;

  readonly contactPreferences = [
    { label: 'Email', value: 'email' },
    { label: 'Phone', value: 'phone' },
    { label: 'SMS', value: 'sms' },
  ];

  readonly profileForm = new FormGroup({
    username: new FormControl({ value: '', disabled: true }, { nonNullable: true }),
    role: new FormControl({ value: '', disabled: true }, { nonNullable: true }),
    email: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.email],
    }),
    contact_preference: new FormControl('email', {
      nonNullable: true,
      validators: [Validators.required],
    }),
    display_name: new FormControl('', { nonNullable: true }),
    phone: new FormControl('', { nonNullable: true }),
  });

  loading = true;
  saving = false;
  imageUploading = false;
  imageDeleting = false;
  profileImageUrl = '';
  imagePreviewUnavailable = true;
  cameraSupported = false;
  cameraActive = false;
  cameraError = '';
  capturedImagePreviewUrl = '';
  mediaStream: MediaStream | null = null;
  errorMessage = '';
  successMessage = '';
  private destroy$ = new Subject<void>();
  private pendingCameraFile: File | null = null;
  private currentProfile: UserProfile | null = null;

  constructor(
    private readonly authService: AuthService,
    private readonly cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.cameraSupported = typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia;
    this.loadProfile();
  }

  ngOnDestroy(): void {
    this.resetCameraState();
    this.revokeProfileImageUrl();
    this.destroy$.next();
    this.destroy$.complete();
  }

  loadProfile(): void {
    this.loading = true;
    this.errorMessage = '';
    this.successMessage = '';
    this.profileForm.disable();
    this.cdr.markForCheck();

    this.authService.getProfile()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (profile) => {
          this.patchProfile(profile);
          this.authService.applyProfile(profile);
          this.currentProfile = profile;
          this.loading = false;
          this.profileForm.enable();
          this.profileForm.controls.username.disable();
          this.profileForm.controls.role.disable();
          this.loadProfileImage(profile);
          this.cdr.markForCheck();
        },
        error: (err) => {
          this.errorMessage =
            err?.error?.message || 'Unable to load your profile. Please refresh and try again.';
          this.currentProfile = null;
          this.loading = false;
          this.profileForm.enable();
          this.profileForm.controls.username.disable();
          this.profileForm.controls.role.disable();
          this.cdr.markForCheck();
        },
      });
  }

  saveProfile(): void {
    if (this.profileForm.invalid) {
      this.profileForm.markAllAsTouched();
      this.cdr.markForCheck();
      return;
    }

    const payload = {
      email: this.profileForm.controls.email.value.trim(),
      contact_preference: this.profileForm.controls.contact_preference.value,
      display_name: this.profileForm.controls.display_name.value.trim(),
      phone: this.profileForm.controls.phone.value.trim(),
    };

    this.saving = true;
    this.errorMessage = '';
    this.successMessage = '';
    this.profileForm.disable();
    this.cdr.markForCheck();

    this.authService.updateProfile(payload)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (profile) => {
          this.patchProfile(profile);
          this.authService.applyProfile(profile);
          this.currentProfile = profile;
          this.successMessage = 'Profile updated successfully.';
          this.saving = false;
          this.profileForm.enable();
          this.profileForm.controls.username.disable();
          this.profileForm.controls.role.disable();
          this.cdr.markForCheck();
        },
        error: (err) => {
          this.errorMessage =
            err?.error?.message || 'Unable to update your profile. Please review your changes and try again.';
          this.saving = false;
          this.profileForm.enable();
          this.profileForm.controls.username.disable();
          this.profileForm.controls.role.disable();
          this.cdr.markForCheck();
        },
      });
  }

  onProfileImageSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] || null;
    input.value = '';
    if (file) {
      this.uploadProfileImage(file);
    }
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
        video: { facingMode: { ideal: 'user' } },
      });
      this.mediaStream = stream;

      if (this.cameraVideo?.nativeElement) {
        this.cameraVideo.nativeElement.srcObject = stream;
        await this.cameraVideo.nativeElement.play().catch(() => undefined);
      }
    } catch {
      this.stopCameraStream();
      this.cameraActive = false;
      this.cameraError = 'Unable to open the camera. Please allow camera access or choose a photo instead.';
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
    this.pendingCameraFile = new File([blob], `profile-photo-${Date.now()}.jpg`, {
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
      this.cameraError = 'Capture a photo before using it for your profile.';
      this.cdr.markForCheck();
      return;
    }

    this.uploadProfileImage(this.pendingCameraFile);
    this.resetCameraState();
  }

  deleteProfileImage(): void {
    this.imageDeleting = true;
    this.errorMessage = '';
    this.successMessage = '';
    this.cdr.markForCheck();

    this.authService.deleteProfileImage()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (profile) => {
          this.currentProfile = profile;
          this.authService.applyProfile(profile);
          this.revokeProfileImageUrl();
          this.imagePreviewUnavailable = true;
          this.successMessage = 'Profile photo removed.';
          this.imageDeleting = false;
          this.cdr.markForCheck();
        },
        error: (err) => {
          this.errorMessage =
            err?.error?.message || 'Unable to remove your profile photo. Please try again.';
          this.imageDeleting = false;
          this.cdr.markForCheck();
        },
      });
  }

  profileInitials(): string {
    const displayName = this.profileForm.controls.display_name.value || this.currentProfile?.display_name || '';
    const username = this.profileForm.controls.username.value || this.currentProfile?.username || '';
    return this.initialsForName(displayName || username);
  }

  private patchProfile(profile: UserProfile): void {
    this.profileForm.patchValue({
      username: profile.username || '',
      role: profile.role || '',
      email: profile.email || '',
      contact_preference: profile.contact_preference || 'email',
      display_name: profile.display_name || '',
      phone: profile.phone || '',
    });
  }

  private uploadProfileImage(file: File): void {
    this.errorMessage = '';
    this.successMessage = '';
    this.cameraError = '';

    if (file.size > 5 * 1024 * 1024) {
      this.errorMessage = 'Please choose an image smaller than 5 MB.';
      this.cdr.markForCheck();
      return;
    }

    const formData = new FormData();
    formData.append('image', file);
    this.imageUploading = true;
    this.cdr.markForCheck();

    this.authService.uploadProfileImage(formData)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (profile) => {
          this.currentProfile = profile;
          this.authService.applyProfile(profile);
          this.successMessage = 'Profile photo updated.';
          this.imageUploading = false;
          this.loadProfileImage(profile);
          this.cdr.markForCheck();
        },
        error: (err) => {
          this.errorMessage =
            err?.error?.message || 'Unable to upload your profile photo. Initials avatar is still available.';
          this.imageUploading = false;
          this.cdr.markForCheck();
        },
      });
  }

  private loadProfileImage(profile: UserProfile): void {
    if (!profile.has_profile_image) {
      this.revokeProfileImageUrl();
      this.imagePreviewUnavailable = true;
      this.cdr.markForCheck();
      return;
    }

    this.authService.getProfileImage()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (imageBlob) => {
          this.revokeProfileImageUrl();
          this.profileImageUrl = URL.createObjectURL(imageBlob);
          this.imagePreviewUnavailable = false;
          this.cdr.markForCheck();
        },
        error: () => {
          this.revokeProfileImageUrl();
          this.imagePreviewUnavailable = true;
          this.cdr.markForCheck();
        },
      });
  }

  private initialsForName(name: string): string {
    const parts = name
      .trim()
      .split(/\s+/)
      .filter(Boolean);
    if (parts.length === 0) {
      return 'U';
    }
    if (parts.length === 1) {
      return parts[0].charAt(0).toUpperCase() || 'U';
    }
    return `${parts[0].charAt(0)}${parts[parts.length - 1].charAt(0)}`.toUpperCase();
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

  private revokeProfileImageUrl(): void {
    if (this.profileImageUrl) {
      URL.revokeObjectURL(this.profileImageUrl);
      this.profileImageUrl = '';
    }
  }
}
