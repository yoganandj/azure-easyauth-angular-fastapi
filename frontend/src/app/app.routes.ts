
import { Routes } from '@angular/router';
import { HomeComponent } from './home.component';
import { UnauthorizedComponent } from './unauthorized.component';
import { AccessDeniedComponent } from './access-denied.component';

export const routes: Routes = [
  { path: '', component: HomeComponent },
  { path: 'unauthorized', component: UnauthorizedComponent },
  { path: 'access-denied', component: AccessDeniedComponent },
  { path: '**', redirectTo: '' }
];
