
import { Component } from '@angular/core';
import { RouterLink, RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink],
  template: `
    <main class="page">
      <nav>
        <a routerLink="/">Home</a>
        <a routerLink="/unauthorized">Unauthorized page</a>
        <a routerLink="/access-denied">Access denied</a>
      </nav>
      <router-outlet />
    </main>
  `
})
export class AppComponent {}
