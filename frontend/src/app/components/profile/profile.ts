import { ChangeDetectionStrategy, ChangeDetectorRef, Component, OnDestroy, OnInit } from '@angular/core';
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
  errorMessage = '';
  successMessage = '';
  private destroy$ = new Subject<void>();

  constructor(
    private readonly authService: AuthService,
    private readonly cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.loadProfile();
  }

  ngOnDestroy(): void {
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
          this.loading = false;
          this.profileForm.enable();
          this.profileForm.controls.username.disable();
          this.profileForm.controls.role.disable();
          this.cdr.markForCheck();
        },
        error: (err) => {
          this.errorMessage =
            err?.error?.message || 'Unable to load your profile. Please refresh and try again.';
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
}
