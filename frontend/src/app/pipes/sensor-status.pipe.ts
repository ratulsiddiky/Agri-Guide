import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
  name: 'sensorStatus',
})
export class SensorStatusPipe implements PipeTransform {
  transform(value: number | string | null | undefined): string {
    const moisture = typeof value === 'string' ? Number(value) : value;

    if (moisture === null || moisture === undefined || Number.isNaN(moisture)) {
      return '';
    }

    if (moisture < 20) {
      return 'Critical';
    }

    if (moisture <= 40) {
      return 'Warning';
    }

    return 'Optimal';
  }
}