import React from 'react';

import {Row, Col, ListGroup, Form, FormCheck, Button, Spinner} from 'react-bootstrap';
import {BsClipboard, BsPlus} from 'react-icons/bs';
import {UserInfoContext} from '../../common/userinfo';
import {confirmationDialog, passwordChangeDialog} from '../../common/confirms';

import "regenerator-runtime/runtime";

function UserEntry(props) {
	const [gone, setGone] = React.useState(false);
	const [processing, setProcessing] = React.useState(false);
	const [admin, setAdmin] = React.useState(props.admin);
	const userInfo = React.useContext(UserInfoContext);

	const deleteMe = () => {
		(async () => {
			// Confirm the deletion
			if (!await confirmationDialog(
				<p>Are you sure you want to delete <code>{props.username}</code>? All of their data will be removed.</p>
			)) {
				return;
			}

			setProcessing(true);

			try {
				const response = await fetch("/api/v1/user/" + props.id, {
					"method": "DELETE"
				});

				if (response.ok)
					setGone(true);
			}
			finally {
				setProcessing(false);
			}
		})();
	};

	const changePassword = () => {
		(async () => {
			const data = await passwordChangeDialog(
				<h3>Enter new password for <code>{props.username}</code></h3>
			);

			if (!data) return;

			setProcessing(true);

			try {
				const response = await fetch("/api/v1/user/" + props.id, {
					"method": "PUT",
					"headers": {"Content-Type": "application/json"},
					"body": JSON.stringify({
						"password": data
					})
				});

				if (!response.ok) alert("failed");
			}
			finally {
				setProcessing(false);
			}
		})();
	};

	const updateAdmin = (e) => {
		(async (value) => {
			setProcessing(true);

			const oldAdmin = admin;

			try {
				setAdmin(value);

				const response = await fetch("/api/v1/user/" + props.id, {
					"method": "PUT",
					"headers": {"Content-Type": "application/json"},
					"body": JSON.stringify({
						"admin": value
					})
				});

				if (!response.ok) {
					throw Error("failed");
				}
			}
			catch (err) {
				setAdmin(oldAdmin);
				alert(err);
			}
			finally {
				setProcessing(false);
			}
		})(e.target.checked);
	};

	if (gone) return <ListGroup.Item>
		deleted
	</ListGroup.Item>;

	if (props.username === userInfo.name) {
		return <ListGroup.Item>
				<Row>
					<Col md lg="5"><h3 className="mb-0 text-dark d-inline">{props.username}</h3> (you) {processing ? <Spinner size="sm" animation="border" /> : null}</Col>
					<Col md lg="7">
						<Form className="align-middle justify-content-end" inline>
							<FormCheck id={"admin-sw-" + props.id} disabled checked={true} type="switch" custom label="Admin" />
							<Button onClick={changePassword} disabled={processing} variant="outline-secondary" className="mx-1">Change Password</Button>
						</Form>
					</Col>
				</Row>
			</ListGroup.Item>;
	}

	return <ListGroup.Item>
		<Row>
			<Col md lg="5"><h3 className="mb-0 d-inline text-dark">{props.username}</h3> {processing ? <Spinner size="sm" animation="border" /> : null}</Col>
			<Col md lg="7">
				<Form className="align-middle justify-content-end" inline>
					<FormCheck onChange={updateAdmin} checked={admin} disabled={processing} id={"admin-sw-" + props.id} type="switch" custom label="Admin" />
					<Button disabled={processing} variant="outline-secondary" onClick={changePassword} className="mx-1">Change Password</Button>
					<Button disabled={processing} variant="danger" onClick={deleteMe}>Delete</Button>
				</Form>
			</Col>
		</Row>
	</ListGroup.Item>;
}

function Users() {
	const [users, setUsers] = React.useState(null);

	React.useEffect(() => {
		(async ()=>{
			const response = await fetch("/api/v1/user");
			const {users} = await response.json();

			setUsers(users);
		})();
	}, []);

	if (users === null) {
		return <ListGroup className="bg-light">
			<ListGroup.Item>loading... <Spinner size="sm" animation="border" /></ListGroup.Item>
		</ListGroup>;
	}

	return <ListGroup className="bg-light">
		{users.map((user) => <UserEntry username={user.username} key={user.id} id={user.id} admin={user.admin} />)}
	</ListGroup>
}

export default Users;
