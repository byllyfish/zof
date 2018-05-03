

async def run(*instances):
	dispatcher = Dispatcher(*instances)

	async with Driver(dispatcher) as driver:
		await driver.listen('6653')
		await dispatcher.run()
