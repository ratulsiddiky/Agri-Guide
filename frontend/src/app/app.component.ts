import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink, RouterOutlet } from '@angular/router';
import { AuthService } from './services/auth.service';
import { GlobalAlert } from './components/shared/global-alert/global-alert';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, CommonModule, GlobalAlert],
  templateUrl: './app.html',
  styleUrl: './app.css',
})

export class AppComponent {
  title = 'smart-agri-guide-frontend';
  constructor(
    public auth: AuthService,
    private readonly router: Router
  ) {}

  logout() {
    this.auth.logout().subscribe({
      next: () => void this.router.navigate(['/login']),
      error: () => {
        this.auth.clearSession();
        void this.router.navigate(['/login']);
      },
    });
  }
}
