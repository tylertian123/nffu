import {Row, Col} from 'react-bootstrap';

import {UserInfoProvider, UserInfoContext, AdminOnly} from './common/userinfo';

function Home() {
	const userinfo = React.useContext(UserInfoContext);

	return (<>
		<h1>Hello, <b>{userinfo.name}</b></h1>
		<AdminOnly>
			<p>You are logged in with <i>administrative</i> privileges.</p>
		</AdminOnly>
	</>);
}

export default Home;
