import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { provideRouter } from '@angular/router';
import { AuthService, UpdateProfileRequest, UserProfile } from '../../services/auth.service';

import { Profile } from './profile';

describe('Profile', () => {
  let component: Profile;
  let fixture: ComponentFixture<Profile>;
  let profileResponse: UserProfile;
  let updatePayload: UpdateProfileRequest | null;

  beforeEach(async () => {
    profileResponse = {
      user_id: 'user-1',
      username: 'farmer_one',
      email: 'farmer@example.com',
      role: 'user',
      contact_preference: 'email',
      display_name: 'Farmer One',
      phone: '07123 456789',
    };
    updatePayload = null;

    await TestBed.configureTestingModule({
      imports: [Profile],
      providers: [
        provideRouter([]),
        {
          provide: AuthService,
          useValue: {
            getProfile: () => of(profileResponse),
            updateProfile: (payload: UpdateProfileRequest) => {
              updatePayload = payload;
              return of({ ...profileResponse, ...payload });
            },
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(Profile);
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
  });

  it('should render loaded profile details', () => {
    expect(component).toBeTruthy();
    expect(component.profileForm.controls.username.value).toBe('farmer_one');
    expect(component.profileForm.controls.role.value).toBe('user');
    expect(component.profileForm.controls.email.value).toBe('farmer@example.com');
    expect(component.profileForm.controls.display_name.value).toBe('Farmer One');
  });

  it('should save only editable profile fields', () => {
    component.profileForm.patchValue({
      username: 'renamed_user',
      role: 'admin',
      email: 'updated@example.com',
      contact_preference: 'sms',
      display_name: 'Updated Farmer',
      phone: '07000 000000',
    });

    component.saveProfile();

    expect(updatePayload).toEqual({
      email: 'updated@example.com',
      contact_preference: 'sms',
      display_name: 'Updated Farmer',
      phone: '07000 000000',
    });
    expect(component.successMessage).toBe('Profile updated successfully.');
  });

  it('should show an error message when saving fails', async () => {
    const authService = TestBed.inject(AuthService) as unknown as {
      updateProfile: (payload: UpdateProfileRequest) => unknown;
    };
    authService.updateProfile = () =>
      throwError(() => ({ error: { message: 'Profile update failed' } }));

    component.saveProfile();
    fixture.detectChanges();
    await fixture.whenStable();

    expect(component.errorMessage).toBe('Profile update failed');
  });
});
