import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NotificationService } from '../../../services/notification.service';

@Component({
  selector: 'app-global-alert',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './global-alert.html',
  styleUrl: './global-alert.css',
})
export class GlobalAlert {
  constructor(public notificationService: NotificationService) {}
}
