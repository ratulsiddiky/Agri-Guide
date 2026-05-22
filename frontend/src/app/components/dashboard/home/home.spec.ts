import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { Home } from './home';

import { provideRouter } from '@angular/router';
import { AuthService } from '../../../services/auth.service';
import { FarmService } from '../../../services/farm.service';

describe('Home', () => {
  let component: Home;
  let fixture: ComponentFixture<Home>;

  beforeEach(async () => {
    const authServiceStub = {
      currentUserSignal: () => ({ username: 'farmer-1', role: 'user', token: 'x' }),
    } as unknown as AuthService;

    const farmServiceStub = {
      getFarms: () =>
        of({
          data: [],
          pagination: { page: 1, limit: 1, total: 5, has_next: false },
        }),
    } as unknown as FarmService;

    await TestBed.configureTestingModule({
      imports: [Home],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: authServiceStub },
        { provide: FarmService, useValue: farmServiceStub },
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(Home);
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
