
import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  standalone: true,
  selector: 'app-access-denied',
  imports: [RouterLink],
  template: `
    <section class="card">
      <h1>Access denied</h1>
      <p class="muted">
        You are signed in, but your account does not have the role required for this action.
        Contact your application administrator if you believe you should have access.
      </p>
      <div class="actions">
        <a class="button primary" routerLink="/">Return home</a>
      </div>
    </section>
  `
})
export class AccessDeniedComponent {}
