import React from 'react';

import {UserInfoProvider, UserInfoContext, AdminOnly} from '../common/userinfo';
import Alert from 'react-bootstrap/Alert';
import Button from 'react-bootstrap/Button';
import ButtonGroup from 'react-bootstrap/ButtonGroup';

import "regenerator-runtime/runtime";

function ConstantAlerts(props) {
	const extraUserInfo = props.extraUserInfo;

	const alerts = [
		[extraUserInfo.lockbox_error, 
				<Alert variant="warning">There were errors when we last tried to fill in your form. You should probably see what they are <i>hereTODO</i></Alert>],
		[!extraUserInfo.has_lockbox_integration,
				<Alert variant="danger">Something went wrong while agreeing to the warnings and disclaimers and we don't have a place to store your credentials; please <a href="/signup/eula">click here</a> to try again.</Alert>]
	];

	if (alerts.reduce((a, [b, _]) => a || b, false)) {
		return <>
			<hr />
			{alerts.map(([a, val]) => a && val)}
		</>
	}
	else return null;
}

function Home() {
	const userinfo = React.useContext(UserInfoContext);

	const [extraUserInfo, setEUI] = React.useState(null);

	React.useEffect(() => {
		(async ()=>{
			const response = await fetch("/api/v1/me");
			setEUI(await response.json());
		})();
	}, []);

	return (<>
		<h1>Hello, <b>{userinfo.name}</b></h1>
		<AdminOnly>
			<p>You are logged in with <i>administrative</i> privileges.</p>
		</AdminOnly>
		{extraUserInfo !== null && <ConstantAlerts extraUserInfo={extraUserInfo}/>}
		<hr />
		<h2>Quick Actions</h2>
		<hr />
		<ButtonGroup vertical>
			<Button>Change Password</Button>
			<Button variant="danger">Delete Account</Button>
		</ButtonGroup>
	</>);
}

export default Home;
