import "./css/boot.scss";

// Main logged-in page.
// Login page (and all non-logged-in flow) is handled in login.js

import ReactDOM from 'react-dom';
import React from 'react';

import Container from 'react-bootstrap/Container';

class App extends React.Component {
	render() {
		return <Container>
			<p> hi! </p>
		</Container>;
	}
}

const mount = document.getElementById("mount");
ReactDOM.render(<App />, mount);
