
import { Component } from '@angular/core';

@Component({
  standalone: true,
  selector: 'app-unauthorized',
  template: `
    <section class="card">
      <h1>Sign-in required</h1>
      <p class="muted">
        You are not signed in, or your application session is no longer available.
        Sign in with your organizational Microsoft account to continue.
      </p>
      <div class="actions">
        <button class="primary" (click)="signIn()">Sign in</button>
        <button class="secondary" (click)="goHome()">Try again</button>
      </div>
    </section>
  `
})
export class UnauthorizedComponent {
  signIn(): void {
    // This endpoint is handled by Azure App Service Easy Auth.
    window.location.assign('/.auth/login/aad?post_login_redirect_uri=%2F');
  }

  goHome(): void {
    window.location.assign('/');
  }
}
