import { Injectable, signal } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable } from 'rxjs';
import { tap } from 'rxjs/operators';
import { User } from '../models/user.model';
import { environment } from '../../environments/environment';

export interface AuthResponse {
  token: string;
  username: string;
  role?: string;
  user_id?: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
}

export interface RegisterResponse {
  message: string;
  verification_link?: string;
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
      .pipe(tap((response) => this.setSession(response)));
  }

  register(payload: RegisterRequest): Observable<RegisterResponse> {
    return this.http.post<RegisterResponse>(`${this.baseUrl}/users/register`, {
      ...payload,
      role: 'user',
      contact_preference: 'email',
    });
  }


  verifyEmail(verificationLink: string): Observable<{ message: string }> {
    return this.http.get<{ message: string }>(verificationLink);
  }

  logout() {
    return this.http
      .get(`${this.baseUrl}/logout`)
      .pipe(tap(() => this.clearSession()));
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

    this.currentUserSignal.set({
      _id: data.user_id,
      username: data.username,
      role: data.role,
      token: data.token,
    });
  }

  clearSession() {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('username');
    localStorage.removeItem('role');
    localStorage.removeItem('user_id');
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
      username,
      role: localStorage.getItem('role') || undefined,
      token,
    };
  }
}
