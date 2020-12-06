import React from 'react';

import {UserInfoProvider, UserInfoContext, AdminOnly} from '../common/userinfo';
import Alert from 'react-bootstrap/Alert';

import "regenerator-runtime/runtime";

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
		{extraUserInfo === null ? null : (<>
			<hr />
			{extraUserInfo.lockbox_error ? (
				<Alert variant="warning">There were errors when we last tried to fill in your form. You should probably see what they are <i>hereTODO</i></Alert>
			) : null}
			{!extraUserInfo.has_lockbox_integration ? (
					<Alert variant="danger">Something went wrong while agreeing to the warnings and disclaimers and we don't have a place to store your credentials; please <a href="/signup/eula">click here</a> to try again.</Alert>
			) : null}
		</>)}
	</>);
}

export default Home;
