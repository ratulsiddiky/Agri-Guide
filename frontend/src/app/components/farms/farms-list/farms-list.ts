import {
  AfterViewInit,
  Component,
  OnInit,
  OnDestroy,
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  ElementRef,
  ViewChild,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import * as L from 'leaflet';
import { FarmService } from '../../../services/farm.service';
import { Farm } from '../../../models/farm.model';
import { SensorStatusPipe } from '../../../pipes/sensor-status.pipe';
import { AuthService } from '../../../services/auth.service';

interface FarmMapPoint {
  farm: Farm;
  lat: number;
  lng: number;
  approximate: boolean;
}

@Component({
  selector: 'app-farms-list',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, SensorStatusPipe],
  templateUrl: './farms-list.html',
  styleUrl: './farms-list.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FarmsList implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('farmMap', { static: false })
  private farmMapElement?: ElementRef<HTMLElement>;

  farms: Farm[] = [];
  mapFarms: Farm[] = [];
  query = '';
  sortBy = 'name-asc';
  page = 1;
  readonly pageSize = 9;
  totalFarms = 0;
  hasNext = false;
  loading = true;
  error = false;
  errorMessage = '';
  mapMessage = 'Loading your farm map...';
  deletingFarmId = '';
  showMyFarms = false;
  private mapReady = false;
  private mapDataLoaded = false;
  private leafletMap: L.Map | null = null;
  private markerLayers: L.Marker[] = [];
  private mapResizeTimer: number | undefined;
  private readonly farmMarkerIcon = L.icon({
    iconUrl: 'assets/leaflet/marker-icon.png',
    iconRetinaUrl: 'assets/leaflet/marker-icon-2x.png',
    shadowUrl: 'assets/leaflet/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41],
    shadowAnchor: [12, 41],
  });
  private destroy$ = new Subject<void>();

  constructor(
    private readonly farmService: FarmService,
    public readonly authService: AuthService,
    private readonly cdr: ChangeDetectorRef
  ) {}

  private getErrorMessage(error: unknown, fallback: string): string {
    const backendMessage = (error as { error?: { message?: unknown } } | null)?.error
      ?.message;

    return typeof backendMessage === 'string' && backendMessage.trim()
      ? backendMessage
      : fallback;
  }

  ngOnInit(): void {
    this.loadFarms();
    this.loadMapFarms();
  }

  ngAfterViewInit(): void {
    this.mapReady = true;
    this.renderFarmMap();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
    if (this.mapResizeTimer !== undefined) {
      window.clearTimeout(this.mapResizeTimer);
    }
    this.leafletMap?.remove();
    this.leafletMap = null;
    this.markerLayers = [];
  }

  toggleMyFarms(): void {
    this.showMyFarms = !this.showMyFarms;
    this.query = '';
    this.loadFarms(1);
  }

  loadFarms(page = this.page): void {
    this.loading = true;
    this.farms = [];
    this.error = false;
    this.errorMessage = '';
    this.page = page;
    this.cdr.markForCheck();

    const request = this.showMyFarms
      ? this.farmService.getMyFarms(this.page, this.pageSize)
      : this.farmService.getFarms(this.page, this.pageSize);

    request
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response) => {
          this.totalFarms = response.pagination.total;
          this.hasNext = response.pagination.has_next;
          this.farms = this.sortFarms(response.data);
          this.loading = false;
          this.cdr.markForCheck();
        },
        error: (err) => {
          this.error = true;
          this.errorMessage = this.getErrorMessage(
            err,
            'Could not connect to the server. Please make sure the backend is running on port 5001.'
          );
          this.loading = false;
          this.cdr.markForCheck();
        },
      });
  }


  onSearch(): void {
    const searchTerm = this.query.trim();

    if (!searchTerm) {
      this.loadFarms(1);
      return;
    }

    this.loading = true;
    this.farms = [];
    this.error = false;
    this.errorMessage = '';
    this.cdr.markForCheck();

    this.farmService.searchFarms(searchTerm)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (data) => {
          this.page = 1;
          this.totalFarms = data.length;
          this.hasNext = false;
          this.farms = this.sortFarms(data);
          this.loading = false;
          this.cdr.markForCheck();
        },
        error: (err) => {
          console.error(
            this.getErrorMessage(
              err,
              `Unable to search farms for '${searchTerm}'. Please try a different term.`
            )
          );
          this.error = true;
          this.errorMessage = this.getErrorMessage(
            err,
            'Search failed. Please try a different term.'
          );
          this.loading = false;
          this.cdr.markForCheck();
        },
      });
  }


  clearSearch(): void {
    if (!this.query) {
      return;
    }

    this.query = '';
    this.loadFarms(1);
  }


  loadMapFarms(): void {
    this.farmService.getMyFarms(1, 100)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response) => {
          this.mapFarms = response.data;
          this.mapDataLoaded = true;
          this.mapMessage = this.mapFarms.length
            ? ''
            : 'Create a farm to see it on your map.';
          this.renderFarmMap();
          this.cdr.markForCheck();
        },
        error: (err) => {
          this.mapDataLoaded = true;
          this.mapMessage = this.getErrorMessage(
            err,
            'Unable to load your farm map right now.'
          );
          this.cdr.markForCheck();
        },
      });
  }


  private renderFarmMap(): void {
    if (!this.mapReady || !this.mapDataLoaded || !this.farmMapElement?.nativeElement) {
      return;
    }

    this.configureLeafletMarkerIcons();

    if (!this.leafletMap) {
      this.leafletMap = L.map(this.farmMapElement.nativeElement, {
        scrollWheelZoom: false,
      }).setView([54.6, -5.93], 6);
      this.leafletMap.createPane('farmMarkers');
      const markerPane = this.leafletMap.getPane('farmMarkers');
      if (markerPane) {
        markerPane.style.zIndex = '650';
        markerPane.style.pointerEvents = 'none';
      }

      L
        .tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          attribution: '&copy; OpenStreetMap contributors',
          maxZoom: 19,
        })
        .addTo(this.leafletMap);

    }

    this.markerLayers.forEach((marker) => this.leafletMap?.removeLayer(marker));
    this.markerLayers = [];

    const points = this.mapFarms.map((farm) => this.farmMapPoint(farm));
    const markers = points.map((point) => this.createFarmMarker(point));
    this.markerLayers = markers;

    if (markers.length > 0) {
      this.leafletMap.fitBounds(L.featureGroup(markers).getBounds(), {
        padding: [24, 24],
        maxZoom: 11,
      });
      this.mapMessage = points.some((point) => point.approximate)
        ? 'Some markers use approximate demo coordinates.'
        : '';
    }

    this.scheduleMapResize();
  }


  private configureLeafletMarkerIcons(): void {
    delete (L.Icon.Default.prototype as { _getIconUrl?: unknown })._getIconUrl;
    L.Icon.Default.mergeOptions({
      iconRetinaUrl: 'assets/leaflet/marker-icon-2x.png',
      iconUrl: 'assets/leaflet/marker-icon.png',
      shadowUrl: 'assets/leaflet/marker-shadow.png',
    });
  }


  private createFarmMarker(point: FarmMapPoint): L.Marker {
    const marker = L.marker([point.lat, point.lng], {
      icon: this.farmMarkerIcon,
      pane: 'farmMarkers',
      keyboard: true,
      riseOnHover: true,
      riseOffset: 300,
    }).bindPopup(this.markerPopup(point), {
      closeButton: true,
      autoPan: true,
      maxWidth: 260,
    });

    marker.on('click', () => marker.openPopup());
    marker.addTo(this.leafletMap as L.Map);
    return marker;
  }


  private scheduleMapResize(): void {
    if (this.mapResizeTimer !== undefined) {
      window.clearTimeout(this.mapResizeTimer);
    }

    this.mapResizeTimer = window.setTimeout(() => {
      this.leafletMap?.invalidateSize();
    }, 120);
  }


  private farmMapPoint(farm: Farm): FarmMapPoint {
    const explicitLat = this.toNumber(farm.latitude);
    const explicitLng = this.toNumber(farm.longitude);
    if (explicitLat !== null && explicitLng !== null) {
      return { farm, lat: explicitLat, lng: explicitLng, approximate: false };
    }

    const location = farm.location;
    if (location && typeof location === 'object' && Array.isArray(location.coordinates)) {
      const [lng, lat] = location.coordinates;
      if (typeof lat === 'number' && typeof lng === 'number') {
        return { farm, lat, lng, approximate: false };
      }
    }

    if (typeof location === 'string') {
      const match = location.match(/POINT\s*\(\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s*\)/i);
      if (match) {
        return {
          farm,
          lat: Number(match[2]),
          lng: Number(match[1]),
          approximate: false,
        };
      }
    }

    const areaName = String(farm.address?.area_name || '').toLowerCase();
    const nearLondon = areaName.includes('london');
    return {
      farm,
      lat: nearLondon ? 51.5072 : 54.5973,
      lng: nearLondon ? -0.1276 : -5.9301,
      approximate: true,
    };
  }


  private markerPopup(point: FarmMapPoint): string {
    const farm = point.farm;
    const farmName = this.escapeHtml(farm.farm_name || 'Unnamed farm');
    const cropType = this.escapeHtml(farm.crop_type || 'Not specified');
    const moisture = this.escapeHtml(this.soilMoistureLabel(farm));
    const farmId = this.escapeHtml(farm._id || '');
    const locationLabel = point.approximate
      ? '<p class="map-popup-note">Approximate demo location</p>'
      : '';

    return `
      <div class="farm-map-popup">
        <strong>${farmName}</strong>
        <span>Crop: ${cropType}</span>
        <span>Soil moisture: ${moisture}</span>
        ${locationLabel}
        <a class="map-popup-link" href="/farms/${farmId}">
          View farm details
        </a>
      </div>
    `;
  }


  private soilMoistureLabel(farm: Farm): string {
    const sensor = farm.sensors?.find((item) => {
      const type = String(item.type || '').trim().toLowerCase().replace(' ', '_');
      return type === 'soil_moisture';
    });

    const latestReading = sensor?.readings?.[sensor.readings.length - 1]?.value;
    const value = sensor?.value ?? latestReading;
    const unit = typeof sensor?.unit === 'string' ? sensor.unit : '%';

    return value === undefined || value === null ? 'Not available' : `${value}${unit}`;
  }


  private toNumber(value: unknown): number | null {
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value;
    }

    if (typeof value === 'string' && value.trim()) {
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : null;
    }

    return null;
  }


  private escapeHtml(value: string): string {
    return value.replace(/[&<>"']/g, (char) => {
      const replacements: Record<string, string> = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;',
      };
      return replacements[char];
    });
  }


  onSortChange(): void {
    this.farms = this.sortFarms(this.farms);
    this.cdr.markForCheck();
  }


  nextPage(): void {
    if (!this.query.trim() && this.hasNext && !this.loading) {
      this.loadFarms(this.page + 1);
    }
  }


  previousPage(): void {
    if (!this.query.trim() && this.page > 1 && !this.loading) {
      this.loadFarms(this.page - 1);
    }
  }


  deleteFarm(farm: Farm): void {
    const farmId = farm._id || '';
    const farmName = farm.farm_name || 'this farm';

    if (!farmId) {
      this.error = true;
      this.errorMessage = 'Unable to delete farm because the identifier is missing.';
      this.cdr.markForCheck();
      return;
    }

    const confirmed = window.confirm(
      `Are you sure you want to delete ${farmName}? This action cannot be undone.`
    );

    if (!confirmed) {
      return;
    }

    this.deletingFarmId = farmId;
    this.error = false;
    this.errorMessage = '';
    this.cdr.markForCheck();

    this.farmService.deleteFarm(farmId)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => {
          this.deletingFarmId = '';
          if (this.query.trim()) {
            this.onSearch();
            return;
          }
          this.loadFarms(this.page);
          this.cdr.markForCheck();
        },
        error: (err) => {
          this.deletingFarmId = '';
          this.error = true;
          this.errorMessage = this.getErrorMessage(
            err,
            'Delete failed. You may need admin permissions to remove this farm.'
          );
          this.cdr.markForCheck();
        },
      });
  }


  private sortFarms(farms: Farm[]): Farm[] {
    const sorted = [...farms];

    switch (this.sortBy) {
      case 'name-desc':
        return sorted.sort((a, b) =>
          (b.farm_name || '').localeCompare(a.farm_name || '')
        );
      case 'crop-asc':
        return sorted.sort((a, b) =>
          (a.crop_type || '').localeCompare(b.crop_type || '')
        );
      case 'sensors-desc':
        return sorted.sort(
          (a, b) => (b.sensors?.length || 0) - (a.sensors?.length || 0)
        );
      case 'name-asc':
      default:
        return sorted.sort((a, b) =>
          (a.farm_name || '').localeCompare(b.farm_name || '')
        );
    }
  }
}
