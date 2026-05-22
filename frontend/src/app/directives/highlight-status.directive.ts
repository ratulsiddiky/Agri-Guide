import { Directive, ElementRef, Input, Renderer2 } from '@angular/core';

@Directive({
  selector: '[appHighlightStatus]',
  standalone: true,
})
export class HighlightStatusDirective {
  constructor(
    private readonly elementRef: ElementRef<HTMLElement>,
    private readonly renderer: Renderer2
  ) {}

  /**
   * Applies status-based highlighting for warning/ok values.
   */
  @Input('appHighlightStatus')
  set statusValue(value: string | number | null | undefined) {
    this.applyStyles(value);
  }

  /**
   * Resolves warning/ok semantics and updates element styles.
   */
  private applyStyles(value: string | number | null | undefined): void {
    const isWarning = this.isWarningValue(value);

    if (isWarning) {
      this.renderer.setStyle(this.elementRef.nativeElement, 'background-color', '#f8d7da');
      this.renderer.setStyle(this.elementRef.nativeElement, 'border', '1px solid #f5c6cb');
      return;
    }

    this.renderer.setStyle(this.elementRef.nativeElement, 'background-color', '#d4edda');
    this.renderer.setStyle(this.elementRef.nativeElement, 'border', '1px solid #c3e6cb');
  }

  /**
   * Evaluates whether an input value should be treated as warning state.
   */
  private isWarningValue(value: string | number | null | undefined): boolean {
    if (value === null || value === undefined) {
      return false;
    }

    if (typeof value === 'number') {
      return value < 20;
    }

    const trimmed = value.trim();
    if (!trimmed) {
      return false;
    }

    if (trimmed.toUpperCase() === 'WARNING') {
      return true;
    }

    if (trimmed.toUpperCase() === 'OK') {
      return false;
    }

    const numericValue = Number(trimmed);
    if (!Number.isNaN(numericValue)) {
      return numericValue < 20;
    }

    return false;
  }
}
