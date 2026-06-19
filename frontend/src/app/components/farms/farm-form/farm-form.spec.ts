import { ComponentFixture, TestBed } from '@angular/core/testing';
import { convertToParamMap, ActivatedRoute, Router } from '@angular/router';
import { of } from 'rxjs';
import { FarmForm } from './farm-form';
import { ApiService } from '../../../services/api.service';

describe('FarmForm', () => {
  let component: FarmForm;
  let fixture: ComponentFixture<FarmForm>;
  let apiServiceSpy: ApiService;
  let updateFarmCalled = false;

  beforeEach(async () => {
    updateFarmCalled = false;

    apiServiceSpy = {
      getFarmById: () =>
        of({
          _id: 'farm-1',
          farm_name: 'North Field',
          crop_type: 'Wheat',
          region: 'Belfast',
          postcode: 'BT1 1AA',
          address: { area_name: 'Belfast', postcode: 'BT1 1AA' },
          latitude: 54.5973,
          longitude: -5.9301,
          location_source: 'manual_coordinates',
        } as never),
      createFarm: () => of({ message: 'Created', farm_id: 'new-farm' }),
      updateFarm: () => {
        updateFarmCalled = true;
        return of({ message: 'Updated' });
      },
    } as unknown as ApiService;

    await TestBed.configureTestingModule({
      imports: [FarmForm],
      providers: [
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: {
              paramMap: convertToParamMap({ id: 'farm-1' }),
            },
          },
        },
        {
          provide: Router,
          useValue: {
            navigate: () => Promise.resolve(true),
          },
        },
        { provide: ApiService, useValue: apiServiceSpy },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(FarmForm);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should call updateFarm on valid form submit in edit mode', () => {
    component.farmForm.setValue({
      farm_name: 'Updated Farm',
      crop_type: 'Corn',
      address_line: '12 Field Lane',
      city: 'Belfast',
      region: 'Antrim',
      postcode: 'BT1 1AA',
      country: 'United Kingdom',
      latitude: '54.5973',
      longitude: '-5.9301',
      location_source: 'manual_coordinates',
    });

    component.onSubmit();

    expect(updateFarmCalled).toBe(true);
  });
});
