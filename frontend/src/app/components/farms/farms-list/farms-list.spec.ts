import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { provideRouter } from '@angular/router';

import { FarmsList } from './farms-list';
import { FarmService } from '../../../services/farm.service';

describe('FarmsList', () => {
  let component: FarmsList;
  let fixture: ComponentFixture<FarmsList>;
  let farmServiceSpy: FarmService;
  let deletedFarmId = '';

  beforeEach(async () => {
    deletedFarmId = '';
    farmServiceSpy = {
      getFarms: () =>
        of({
          data: [],
          pagination: { page: 1, limit: 9, total: 0, has_next: false },
        }),
      searchFarms: () => of([]),
      deleteFarm: (id: string) => {
        deletedFarmId = id;
        return of(void 0);
      },
    } as unknown as FarmService;

    await TestBed.configureTestingModule({
      imports: [FarmsList],
      providers: [
        provideRouter([]),
        { provide: FarmService, useValue: farmServiceSpy },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(FarmsList);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should call deleteFarm when user confirms deletion', () => {
    const originalConfirm = window.confirm;
    let reloaded = false;
    component.loadFarms = () => {
      reloaded = true;
    };
    window.confirm = () => true;

    component.deleteFarm({ _id: 'farm-1', farm_name: 'North Field' });

    expect(deletedFarmId).toBe('farm-1');
    expect(reloaded).toBe(true);

    window.confirm = originalConfirm;
  });
});
