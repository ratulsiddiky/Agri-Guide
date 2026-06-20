import { Injectable, signal } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, of } from 'rxjs';
import { catchError, finalize, map, switchMap, tap } from 'rxjs/operators';
import { User } from '../models/user.model';
import { environment } from '../../environments/environment';

export interface AuthResponse {
  token: string;
  username: string;
  role?: string;
  user_id?: string;
  display_name?: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
}

export interface RegisterResponse {
  message: string;
  verification_link?: string;
  email_verification_required?: boolean;
  email_sent?: boolean;
}

export interface UserProfile {
  user_id: string;
  username: string;
  email: string;
  role: string;
  contact_preference?: string;
  created_at?: string;
  display_name?: string;
  phone?: string;
  has_profile_image?: boolean;
}

export interface UpdateProfileRequest {
  email: string;
  contact_preference: string;
  display_name?: string;
  phone?: string;
}

export interface VerificationResponse {
  message: string;
  email_verification_required?: boolean;
  email_sent?: boolean;
}

export interface PasswordResetResponse {
  message: string;
}

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private readonly baseUrl = environment.apiBaseUrl;
  readonly currentUserSignal = signal<User | null>(this.readSession());
  readonly emailVerifiedSuccessfully = signal(false);

  constructor(
    private readonly http: HttpClient,
    private readonly router: Router
  ) {}

  login(username: string, password: string): Observable<AuthResponse> {
    const credentials = `${username}:${password}`;
    
    const safeBase64 = btoa(
      new Uint8Array(new TextEncoder().encode(credentials)).reduce(
        (data, byte) => data + String.fromCharCode(byte),
        ''
      )
    );
  
    const headers = new HttpHeaders({
      Authorization: `Basic ${safeBase64}`,
    });

    return this.http
      .post<AuthResponse>(`${this.baseUrl}/login`, {}, { headers })
      .pipe(
        tap((response) => this.setSession(response)),
        switchMap((response) =>
          this.getProfile().pipe(
            tap((profile) => this.applyProfile(profile)),
            map(() => response),
            catchError(() => of(response))
          )
        )
      );
  }

  register(payload: RegisterRequest): Observable<RegisterResponse> {
    return this.http.post<RegisterResponse>(`${this.baseUrl}/users/register`, {
      ...payload,
      role: 'user',
      contact_preference: 'email',
    });
  }


  verifyEmail(verificationLink: string): Observable<VerificationResponse> {
    return this.http.get<{ message: string }>(verificationLink);
  }

  verifyEmailToken(token: string): Observable<VerificationResponse> {
    return this.http.post<VerificationResponse>(`${this.baseUrl}/users/verify-email`, { token });
  }

  resendVerification(identifier: string): Observable<VerificationResponse> {
    return this.http.post<VerificationResponse>(`${this.baseUrl}/users/resend-verification`, {
      identifier,
    });
  }

  forgotPassword(identifier: string): Observable<PasswordResetResponse> {
    return this.http.post<PasswordResetResponse>(`${this.baseUrl}/users/forgot-password`, {
      identifier,
    });
  }

  resetPassword(token: string, newPassword: string): Observable<PasswordResetResponse> {
    return this.http.post<PasswordResetResponse>(`${this.baseUrl}/users/reset-password`, {
      token,
      new_password: newPassword,
    });
  }

  getProfile(): Observable<UserProfile> {
    return this.http.get<UserProfile>(`${this.baseUrl}/users/me`);
  }

  updateProfile(payload: UpdateProfileRequest): Observable<UserProfile> {
    return this.http.put<UserProfile>(`${this.baseUrl}/users/me`, payload);
  }

  getProfileImage(): Observable<Blob> {
    return this.http.get(`${this.baseUrl}/users/me/profile-image`, {
      responseType: 'blob',
    });
  }

  uploadProfileImage(formData: FormData): Observable<UserProfile> {
    return this.http.post<UserProfile>(`${this.baseUrl}/users/me/profile-image`, formData);
  }

  deleteProfileImage(): Observable<UserProfile> {
    return this.http.delete<UserProfile>(`${this.baseUrl}/users/me/profile-image`);
  }

  logout() {
    return this.http
      .get(`${this.baseUrl}/logout`)
      .pipe(
        catchError(() => of(null)),
        finalize(() => this.clearSession())
      );
  }

  isAuthenticated(): boolean {
    return !!this.currentUserSignal()?.token;
  }

  isLoggedIn(): boolean {
    return this.isAuthenticated();
  }

  getToken(): string {
    return this.currentUserSignal()?.token || '';
  }

  getCurrentUser(): User | null {
    return this.currentUserSignal();
  }

  getUsername(): string {
    return this.currentUserSignal()?.username || '';
  }

  getDisplayName(): string {
    const user = this.currentUserSignal();
    return user?.display_name || user?.username || '';
  }

  getRole(): string {
    return this.currentUserSignal()?.role || '';
  }

  getUserId(): string {
    return this.currentUserSignal()?._id || '';
  }

  setSession(data: AuthResponse) {
    localStorage.setItem('auth_token', data.token);
    localStorage.setItem('username', data.username);

    if (data.role) {
      localStorage.setItem('role', data.role);
    } else {
      localStorage.removeItem('role');
    }

    if (data.user_id) {
      localStorage.setItem('user_id', data.user_id);
    } else {
      localStorage.removeItem('user_id');
    }

    this.clearProfileStorage();
    this.setOptionalStorageValue('display_name', data.display_name);

    this.currentUserSignal.set({
      _id: data.user_id,
      username: data.username,
      role: data.role,
      display_name: data.display_name,
      token: data.token,
    });
  }

  applyProfile(profile: UserProfile): void {
    const currentUser = this.currentUserSignal();

    if (!currentUser) {
      return;
    }

    const nextUser: User = {
      ...currentUser,
      _id: currentUser._id || profile.user_id,
      user_id: currentUser.user_id || profile.user_id,
      username: currentUser.username || profile.username,
      role: currentUser.role || profile.role,
      email: profile.email,
      contact_preference: profile.contact_preference,
      created_at: profile.created_at,
      display_name: profile.display_name?.trim() || '',
      phone: profile.phone,
      has_profile_image: profile.has_profile_image,
    };

    this.setOptionalStorageValue('display_name', nextUser.display_name);
    this.setOptionalStorageValue('email', nextUser.email);
    this.setOptionalStorageValue('contact_preference', nextUser.contact_preference);
    this.setOptionalStorageValue('created_at', nextUser.created_at);
    this.setOptionalStorageValue('phone', nextUser.phone);
    this.setBooleanStorageValue('has_profile_image', nextUser.has_profile_image);
    this.currentUserSignal.set(nextUser);
  }

  clearSession() {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('username');
    localStorage.removeItem('role');
    localStorage.removeItem('user_id');
    this.clearProfileStorage();
    this.currentUserSignal.set(null);
  }

  handleUnauthorized() {
    this.clearSession();
    void this.router.navigate(['/login']);
  }

  private readSession(): User | null {
    const token = localStorage.getItem('auth_token');
    const username = localStorage.getItem('username');

    if (!token || !username) {
      return null;
    }

    return {
      _id: localStorage.getItem('user_id') || undefined,
      user_id: localStorage.getItem('user_id') || undefined,
      username,
      role: localStorage.getItem('role') || undefined,
      email: localStorage.getItem('email') || undefined,
      contact_preference: localStorage.getItem('contact_preference') || undefined,
      created_at: localStorage.getItem('created_at') || undefined,
      display_name: localStorage.getItem('display_name') || undefined,
      phone: localStorage.getItem('phone') || undefined,
      has_profile_image:
        localStorage.getItem('has_profile_image') === null
          ? undefined
          : localStorage.getItem('has_profile_image') === 'true',
      token,
    };
  }

  private setOptionalStorageValue(key: string, value: string | undefined): void {
    const cleanValue = value?.trim();
    if (cleanValue) {
      localStorage.setItem(key, cleanValue);
      return;
    }

    localStorage.removeItem(key);
  }

  private clearProfileStorage(): void {
    localStorage.removeItem('display_name');
    localStorage.removeItem('email');
    localStorage.removeItem('contact_preference');
    localStorage.removeItem('created_at');
    localStorage.removeItem('phone');
    localStorage.removeItem('has_profile_image');
  }

  private setBooleanStorageValue(key: string, value: boolean | undefined): void {
    if (value === undefined) {
      localStorage.removeItem(key);
      return;
    }

    localStorage.setItem(key, String(value));
  }
}
