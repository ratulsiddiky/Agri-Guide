import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HighlightStatusDirective } from './highlight-status.directive';

@Component({
  standalone: true,
  imports: [HighlightStatusDirective],
  template: `<p id="status" [appHighlightStatus]="value">Status</p>`,
})
class TestHostComponent {
  value: string | number = 'OK';
}

describe('HighlightStatusDirective', () => {
  let fixture: ComponentFixture<TestHostComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TestHostComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(TestHostComponent);
  });

  it('should apply warning styles for WARNING value', () => {
    fixture.componentInstance.value = 'WARNING';
    fixture.detectChanges();

    const element = fixture.nativeElement.querySelector('#status') as HTMLElement;
    expect(element.style.backgroundColor).toBe('rgb(248, 215, 218)');
    expect(element.style.border).toContain('rgb(245, 198, 203)');
  });

  it('should apply success styles for values >= 20', () => {
    fixture.componentInstance.value = 42;
    fixture.detectChanges();

    const element = fixture.nativeElement.querySelector('#status') as HTMLElement;
    expect(element.style.backgroundColor).toBe('rgb(212, 237, 218)');
    expect(element.style.border).toContain('rgb(195, 230, 203)');
  });
});
