import React from 'react'
import { Alert, Row, Col } from 'react-bootstrap'

function FlashBox(props) {
	if (window.flashed_msgs) {
		return (<div>
			{window.flashed_msgs.map((x, i) => (
				<Row>
					<Col xs="12">
						<Alert key={i} variant="primary">{x}</Alert>
					</Col>
				</Row>
			))}
		</div>);
	}
	else {
		return (null);
	}
}

export default FlashBox;
