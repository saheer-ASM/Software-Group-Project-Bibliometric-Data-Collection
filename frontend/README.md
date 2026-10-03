# ScholarMetrics frontend

## Routes

| URL | Page | Access |
|---|---|---|
| `/login` | Sign in | signed-out only |
| `/register` | Registration | signed-out only |
| `/forgot-password` | Request a password-reset email | signed-out only |
| `/verify-email` | Waiting for email verification | signed-out only |
| `/reset-password` | Firebase email links (reset password / verify email) | anyone |
| `/dashboard` | Dashboard | signed in |
| `/data-explorer` | Data Explorer (`?author=Name` opens that author) | signed in |
| `/settings` | Profile settings | signed in |
| `/about` | About Us | signed in |
| `/library` | My Library | signed in |
| `/admin` | Feedback & issues admin | signed in, with the admin claim |

Routing uses React Router (`src/App.js`). A signed-out visit to a protected page
redirects to `/login` and returns to that page after logging in. `/` and unknown
paths go to `/dashboard` when signed in, otherwise to `/login`.

## Deploying (single-page app)

The web server must answer every app route with `index.html`; otherwise
refreshing `/dashboard` returns 404. `npm start` already does this in development.

For Nginx, use [deploy/nginx.conf](deploy/nginx.conf). It serves the build, falls
back to `index.html` for app routes, and proxies `/api/` to the backend without
rewriting it. Other hosts need the same rule, for example:

* Netlify `_redirects`: `/* /index.html 200`
* Firebase Hosting: `"rewrites": [{ "source": "**", "destination": "/index.html" }]`

---

## Getting Started with Create React App

This project was bootstrapped with [Create React App](https://github.com/facebook/create-react-app).

## Available Scripts

In the project directory, you can run:

### `npm start`

Runs the app in the development mode.\
Open [http://localhost:3000](http://localhost:3000) to view it in your browser.

The page will reload when you make changes.\
You may also see any lint errors in the console.

### `npm test`

Launches the test runner in the interactive watch mode.\
See the section about [running tests](https://facebook.github.io/create-react-app/docs/running-tests) for more information.

### `npm run build`

Builds the app for production to the `build` folder.\
It correctly bundles React in production mode and optimizes the build for the best performance.

The build is minified and the filenames include the hashes.\
Your app is ready to be deployed!

See the section about [deployment](https://facebook.github.io/create-react-app/docs/deployment) for more information.

### `npm run eject`

**Note: this is a one-way operation. Once you `eject`, you can't go back!**

If you aren't satisfied with the build tool and configuration choices, you can `eject` at any time. This command will remove the single build dependency from your project.

Instead, it will copy all the configuration files and the transitive dependencies (webpack, Babel, ESLint, etc) right into your project so you have full control over them. All of the commands except `eject` will still work, but they will point to the copied scripts so you can tweak them. At this point you're on your own.

You don't have to ever use `eject`. The curated feature set is suitable for small and middle deployments, and you shouldn't feel obligated to use this feature. However we understand that this tool wouldn't be useful if you couldn't customize it when you are ready for it.

## Learn More

You can learn more in the [Create React App documentation](https://facebook.github.io/create-react-app/docs/getting-started).

To learn React, check out the [React documentation](https://reactjs.org/).

### Code Splitting

This section has moved here: [https://facebook.github.io/create-react-app/docs/code-splitting](https://facebook.github.io/create-react-app/docs/code-splitting)

### Analyzing the Bundle Size

This section has moved here: [https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size](https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size)

### Making a Progressive Web App

This section has moved here: [https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app](https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app)

### Advanced Configuration

This section has moved here: [https://facebook.github.io/create-react-app/docs/advanced-configuration](https://facebook.github.io/create-react-app/docs/advanced-configuration)

### Deployment

This section has moved here: [https://facebook.github.io/create-react-app/docs/deployment](https://facebook.github.io/create-react-app/docs/deployment)

### `npm run build` fails to minify

This section has moved here: [https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify](https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify)
